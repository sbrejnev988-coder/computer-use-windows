"""WebSocket remote server — secure remote MCP access with auth + sessions.

Pattern from trycua/cua computer-server/server.py.
Run: python -m computer_use_windows.remote --port 8765 [--token my-secret]

Security (CISA Red Team Audit P2):
  - Mandatory token when binding non-loopback
  - hmac.compare_digest for token comparison
  - Configurable message size limit
  - Operation timeout
"""

import asyncio, base64, hmac, json, logging, os, secrets, sys, time, uuid
from typing import Any, Dict, Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None

# FIXED: relative import from same package, not parent
from .handlers import (
    WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler,
)

logger = logging.getLogger(__name__)

# FIXED: string, not list — os.getenv expects str
DEFAULT_TOKEN_ENV = "COMPUTER_USE_WINDOWS_TOKEN"

HEARTBEAT_INTERVAL = 30   # seconds
HEARTBEAT_TIMEOUT = 90    # seconds
MAX_MESSAGE_SIZE = 50 * 1024 * 1024  # 50 MB
OPERATION_TIMEOUT = 60.0  # seconds


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
        # FIXED: os.getenv with string arg; enforce token on non-loopback
        self.token = token or os.getenv(DEFAULT_TOKEN_ENV)
        if not self.token and host not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError(
                "A token is required when binding to a non-loopback address. "
                f"Set {DEFAULT_TOKEN_ENV} environment variable or pass --token."
            )
        self.sessions: Dict[str, RemoteComputerSession] = {}
        logger.info(
            f"Remote server ws://{host}:{port} "
            f"auth={'token' if self.token else 'NONE (loopback only)'}"
        )

    async def _authenticate(self, websocket) -> bool:
        """Wait for auth message within 5s. If token is set, require it.
        
        FIXED: uses hmac.compare_digest for timing-safe comparison.
        """
        if not self.token:
            return True  # Token not required (loopback-only)
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            msg = json.loads(raw)
            client_token = msg.get("token", "")
            if hmac.compare_digest(client_token, self.token):
                await websocket.send(json.dumps({
                    "status": "ok",
                    "session": msg.get("resume_session", "")
                }))
                return True
            await websocket.send(json.dumps({"status": "error", "error": "Invalid token"}))
            return False
        except (asyncio.TimeoutError, json.JSONDecodeError):
            await websocket.send(json.dumps({
                "status": "error",
                "error": 'Auth required — send {"token":"..."}'
            }))
            return False

    async def handle_message(
        self, session: RemoteComputerSession, msg: Dict[str, Any]
    ) -> Dict[str, Any]:
        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")
        a, acc, f = session.automation, session.accessibility, session.file

        try:
            handlers = {
                "screenshot": lambda: a.screenshot(),
                "screenshot_region": lambda: a.screenshot_region(
                    params.get("x", 0), params.get("y", 0),
                    params.get("width"), params.get("height")
                ),
                "screenshot_window": lambda: a.screenshot_window(params.get("window_id")),
                "get_screen_size": lambda: a.get_screen_size(),
                "get_cursor_position": lambda: a.get_cursor_position(),
                "click": lambda: a.left_click(params.get("x"), params.get("y")),
                "right_click": lambda: a.right_click(params.get("x"), params.get("y")),
                "middle_click": lambda: a.middle_click(params.get("x"), params.get("y")),
                "double_click": lambda: a.double_click(params.get("x"), params.get("y")),
                "move": lambda: a.move_cursor(params["x"], params["y"]),
                "drag": lambda: a.drag_to(
                    params["x"], params["y"],
                    params.get("button", "left"),
                    params.get("duration", 0.5)
                ),
                "scroll": lambda: a.scroll(
                    params.get("scroll_x", 0), params.get("scroll_y", 0)
                ),
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
                "resize_window": lambda: a.resize_window(
                    params["window_id"], params["width"], params["height"]
                ),
                "minimize_window": lambda: a.minimize_window(params["window_id"]),
                "maximize_window": lambda: a.maximize_window(params["window_id"]),
                "close_window": lambda: a.close_window(params["window_id"]),
                "restore_window": lambda: a.restore_window(params["window_id"]),
                # P0 NEW: activate_window
                "activate_window": lambda: a.activate_window(params["window_id"]),
                "list_processes": lambda: a.list_processes(),
                "kill_process": lambda: a.kill_process(params["pid"]),
                "registry_read": lambda: a.registry_read(
                    params["key_path"], params.get("value_name", "")
                ),
                "registry_write": lambda: a.registry_write(
                    params["key_path"], params["value_name"],
                    params["value"], params.get("reg_type", "REG_SZ")
                ),
                "list_services": lambda: a.list_services(),
                "service_status": lambda: a.service_status(params["name"]),
                "service_start": lambda: a.service_start(params["name"]),
                "service_stop": lambda: a.service_stop(params["name"]),
                "service_restart": lambda: a.service_restart(params["name"]),
                "system_info": lambda: a.system_info(),
                "get_file_permissions": lambda: a.get_file_permissions(params["path"]),
                "accessibility_tree": lambda: acc.get_accessibility_tree(),
                "find_element": lambda: acc.find_element(
                    params.get("role"), params.get("title")
                ),
                # UIA NEW tools
                "get_ui_tree": lambda: acc.get_ui_tree(),
                "find_ui_elements": lambda: acc.find_ui_elements(
                    params.get("control_type"),
                    params.get("name"),
                    params.get("automation_id"),
                    params.get("class_name"),
                ),
                "focus_ui_element": lambda: acc.focus_ui_element(params.get("element_id")),
                "invoke_ui_element": lambda: acc.invoke_ui_element(params.get("element_id")),
                "set_ui_value": lambda: acc.set_ui_value(
                    params.get("element_id"), params.get("value")
                ),
                "toggle_ui_element": lambda: acc.toggle_ui_element(params.get("element_id")),
                "select_ui_element": lambda: acc.select_ui_element(params.get("element_id")),
                "expand_ui_element": lambda: acc.expand_ui_element(params.get("element_id")),
                "scroll_ui_element_into_view": lambda: acc.scroll_ui_element_into_view(
                    params.get("element_id")
                ),
                "wait_for_ui_element": lambda: acc.wait_for_ui_element(
                    params.get("control_type"),
                    params.get("name"),
                    params.get("timeout_ms", 5000),
                ),
                "file_read": lambda: f.read_text(params["path"]),
                "file_write": lambda: f.write_text(params["path"], params["content"]),
                "file_read_bytes": lambda: f.read_bytes(
                    params["path"], params.get("offset", 0), params.get("length")
                ),
                "file_write_bytes": lambda: f.write_bytes(
                    params["path"], base64.b64decode(params["content_base64"])
                ),
                "file_exists": lambda: f.file_exists(params["path"]),
                "dir_exists": lambda: f.directory_exists(params["path"]),
                "list_dir": lambda: f.list_dir(params["path"]),
                "create_dir": lambda: f.create_dir(params["path"]),
                "delete_file": lambda: f.delete_file(params["path"]),
                "delete_dir": lambda: f.delete_dir(params["path"]),
                "get_file_size": lambda: f.get_file_size(params["path"]),
                "move_file": lambda: f.move_file(params["src"], params["dst"]),
                "copy_file": lambda: f.copy_file(params["src"], params["dst"]),
                "doctor": lambda: a.system_info(),
            }
            if method not in handlers:
                return {"id": request_id, "error": f"Unknown method: {method}"}
            
            # FIXED: timeout per operation
            result = await asyncio.wait_for(
                asyncio.to_thread(handlers[method]) if not asyncio.iscoroutinefunction(
                    handlers[method].__class__.__call__
                ) else handlers[method](),
                timeout=OPERATION_TIMEOUT
            )
            # Unwrap coroutine if needed
            if asyncio.iscoroutine(result):
                result = await result
            return {"id": request_id, "result": result}
        except asyncio.TimeoutError:
            return {"id": request_id, "error": "Operation timed out"}
        except Exception as e:
            logger.exception(f"Handler error: {method}")
            return {"id": request_id, "error": str(e)}

    async def serve(self, websocket):
        """Handle one WebSocket connection with heartbeat monitoring."""
        session_id = uuid.uuid4().hex[:12]
        session = RemoteComputerSession()
        self.sessions[session_id] = session
        logger.info(f"Session {session_id} connected ({len(self.sessions)} active)")

        try:
            if not await self._authenticate(websocket):
                return

            # Heartbeat task
            async def heartbeat():
                while True:
                    await asyncio.sleep(HEARTBEAT_INTERVAL)
                    try:
                        await websocket.ping()
                    except Exception:
                        break

            hb_task = asyncio.create_task(heartbeat())

            try:
                async for raw in websocket:
                    if len(raw) > MAX_MESSAGE_SIZE:
                        await websocket.send(json.dumps({
                            "id": None, "error": "Message too large"
                        }))
                        continue
                    msg = json.loads(raw)
                    resp = await self.handle_message(session, msg)
                    await websocket.send(json.dumps(resp))
                    session.last_heartbeat = time.time()
            finally:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass

        except ConnectionClosed:
            logger.info(f"Session {session_id} disconnected")
        except Exception as e:
            logger.exception(f"Session {session_id} error")
        finally:
            self.sessions.pop(session_id, None)

    async def start(self):
        """Start WebSocket server."""
        if websockets is None:
            logger.error("websockets not installed — pip install websockets")
            return
        async with websockets.serve(self.serve, self.host, self.port):
            logger.info(
                f"WebSocket server ws://{self.host}:{self.port} "
                f"(sessions={len(self.sessions)})"
            )
            await asyncio.Future()  # run forever


def main() -> None:
    """Synchronous entry point for console script."""
    import argparse
    parser = argparse.ArgumentParser(description="Computer Use Windows Remote Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    server = RemoteComputerServer(args.host, args.port, args.token)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
