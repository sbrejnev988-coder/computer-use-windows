"""WebSocket remote server — secure remote MCP access with auth + sessions.

Pattern from trycua/cua computer-server/server.py.
Run: python -m computer_use_windows.remote --port 8765 [--token my-secret]
"""

import asyncio, base64, json, logging, os, secrets, sys, time, uuid
from typing import Any, Dict, Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None

from ..handlers import (
    WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler,
)

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_ENV = ["REDACTED"]
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 90   # seconds


class RemoteComputerSession:
    """Isolated session per WebSocket client."""
    def __init__(self):
        self.session_id = uuid.uuid4().hex[:12]
        self.automation = WindowsAutomationHandler()
        self.accessibility = WindowsAccessibilityHandler()
        self.file = WindowsFileHandler()
        self.created_at = time.time()
        self.last_heartbeat = time.time()


class RemoteComputerServer:
    """WebSocket server with token auth, session isolation, heartbeat."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765, token: Optional[str] = None):
        self.host = host
        self.port = port
        self.token = token or os.environ.get(DEFAULT_TOKEN_ENV)
        self.sessions: Dict[str, RemoteComputerSession] = {}
        logger.info(f"Remote server ws://{host}:{port} auth={'token' if self.token else 'NONE (127.0.0.1 only)'}")

    async def _authenticate(self, websocket) -> bool:
        """Wait for auth message within 5s. If token is set, require it."""
        if not self.token:
            return True  # No token → open access (safe on 127.0.0.1)
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            msg = json.loads(raw)
            if msg.get("token") == self.token:
                await websocket.send(json.dumps({"status": "ok", "session": msg.get("resume_session", "")}))
                return True
            await websocket.send(json.dumps({"status": "error", "error": "Invalid token"}))
            return False
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.send(json.dumps({"status": "error", "error": "Auth required — send {\"token\":\"...\"}"}))
            return False

    async def handle_message(self, session: RemoteComputerSession, msg: Dict[str, Any]) -> Dict[str, Any]:
        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")
        a, acc, f = session.automation, session.accessibility, session.file

        try:
            handlers = {
                "screenshot": lambda: a.screenshot(),
                "screenshot_region": lambda: a.screenshot_region(params.get("x", 0), params.get("y", 0), params.get("width"), params.get("height")),
                "screenshot_window": lambda: a.screenshot_window(params.get("window_id")),
                "get_screen_size": lambda: a.get_screen_size(),
                "get_cursor_position": lambda: a.get_cursor_position(),
                "click": lambda: a.left_click(params.get("x"), params.get("y")),
                "right_click": lambda: a.right_click(params.get("x"), params.get("y")),
                "middle_click": lambda: a.middle_click(params.get("x"), params.get("y")),
                "double_click": lambda: a.double_click(params.get("x"), params.get("y")),
                "move": lambda: a.move_cursor(params["x"], params["y"]),
                "drag": lambda: a.drag_to(params["x"], params["y"], params.get("button", "left")),
                "scroll": lambda: a.scroll(params.get("scroll_x", 0), params.get("scroll_y", 0)),
                "type": lambda: a.type_text(params["text"]),
                "press_key": lambda: a.press_key(params["key"]),
                "hotkey": lambda: a.hotkey(params["keys"]),
                "clipboard_get": lambda: a.copy_to_clipboard(),
                "clipboard_set": lambda: a.set_clipboard(params["text"]),
                "run_command": lambda: a.run_command(params["command"]),
                "launch": lambda: a.launch(params["app"], params.get("args")),
                "get_current_window": lambda: a.get_current_window_id(),
                "get_app_windows": lambda: a.get_application_windows(params["app"]),
                "list_windows": lambda: a.list_all_windows(),
                "resize_window": lambda: a.resize_window(params["window_id"], params["width"], params["height"]),
                "minimize_window": lambda: a.minimize_window(params["window_id"]),
                "maximize_window": lambda: a.maximize_window(params["window_id"]),
                "close_window": lambda: a.close_window(params["window_id"]),
                "list_processes": lambda: a.list_processes(),
                "kill_process": lambda: a.kill_process(params["pid"]),
                "registry_read": lambda: a.registry_read(params["key_path"], params.get("value_name", "")),
                "registry_write": lambda: a.registry_write(params["key_path"], params["value_name"], params["value"]),
                "service_status": lambda: a.service_status(params["name"]),
                "service_start": lambda: a.service_start(params["name"]),
                "service_stop": lambda: a.service_stop(params["name"]),
                "service_restart": lambda: a.service_restart(params["name"]),
                "list_services": lambda: a.list_services(),
                "system_info": lambda: a.system_info(),
                "get_file_permissions": lambda: a.get_file_permissions(params["path"]),
                "accessibility_tree": lambda: acc.get_accessibility_tree(),
                "find_element": lambda: acc.find_element(params.get("role"), params.get("title")),
                "file_read": lambda: f.read_text(params["path"]),
                "file_write": lambda: f.write_text(params["path"], params["content"]),
                "file_exists": lambda: f.file_exists(params["path"]),
                "list_dir": lambda: f.list_dir(params["path"]),
                "create_dir": lambda: f.create_dir(params["path"]),
                "delete_file": lambda: f.delete_file(params["path"]),
                "delete_dir": lambda: f.delete_dir(params["path"]),
                "file_size": lambda: f.get_file_size(params["path"]),
                "move_file": lambda: f.move_file(params["src"], params["dst"]),
                "copy_file": lambda: f.copy_file(params["src"], params["dst"]),
                "ping": lambda: {"success": True, "session": session.session_id, "uptime": round(time.time() - session.created_at)},
            }

            if method not in handlers:
                return {"id": request_id, "error": f"Unknown method: {method}"}
            result = await handlers[method]()
            return {"id": request_id, "result": result}
        except Exception as e:
            logger.error(f"Error in {method}: {e}")
            return {"id": request_id, "error": str(e)}

    async def _heartbeat_loop(self, session: RemoteComputerSession, websocket):
        """Send periodic pings; terminate on timeout. Task cleans itself up on exit."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    pong = await asyncio.wait_for(websocket.ping(), timeout=10)
                    await pong
                    session.last_heartbeat = time.time()
                except Exception:
                    logger.warning(f"Session {session.session_id} heartbeat lost, closing")
                    break
        except asyncio.CancelledError:
            pass  # Normal cleanup — task cancelled by serve()
        finally:
            self.sessions.pop(session.session_id, None)
            logger.debug(f"Session {session.session_id} cleaned up")

    async def serve(self, websocket):
        remote_addr = websocket.remote_address
        logger.info(f"Connection from {remote_addr}")

        if not await self._authenticate(websocket):
            await websocket.close(1008, "Auth failed")
            return

        session = RemoteComputerSession()
        self.sessions[session.session_id] = session
        logger.info(f"Session {session.session_id} started from {remote_addr}")

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(session, websocket))

        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                    if msg.get("method") == "ping":
                        await websocket.send(json.dumps({"id": msg.get("id"), "result": "pong"}))
                        continue
                    response = await self.handle_message(session, msg)
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"error": "Invalid JSON"}))
        except ConnectionClosed:
            logger.info(f"Session {session.session_id} disconnected")
        except Exception as e:
            logger.error(f"Session {session.session_id} error: {e}")
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task  # Ensure cleanup ran
            except asyncio.CancelledError:
                pass

    async def start(self):
        if websockets is None:
            logger.error("websockets not installed — pip install websockets")
            return
        logger.info(f"WebSocket server ws://{self.host}:{self.port} (sessions={len(self.sessions)})")
        async with websockets.serve(self.serve, self.host, self.port, ping_interval=None):
            await asyncio.Future()


async def main():
    import argparse
    p = argparse.ArgumentParser(description="computer-use-windows remote server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--token", help=f"Auth token (or set {DEFAULT_TOKEN_ENV} env var)")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    server = RemoteComputerServer(host=args.host, port=args.port, token=args.token)
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
