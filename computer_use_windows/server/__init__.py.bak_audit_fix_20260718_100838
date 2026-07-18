"""FastMCP server — Windows desktop control (50+ tools).

Full screen, region, window screenshot; mouse; keyboard; clipboard; shell;
window mgmt; processes; registry; services; system info; accessibility; files.
"""

import base64, logging, sys
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from PIL import Image as PILImage

from ..handlers import (
    WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stderr)

_a = WindowsAutomationHandler()
_acc = WindowsAccessibilityHandler()
_f = WindowsFileHandler()

_sx, _sy = 1.0, 1.0
def _actual(x, y): return int(x * _sx), int(y * _sy)

def _screenshot_result(r):
    """Normalize screenshot handler output to JPEG FastMCP Image."""
    img = PILImage.open(BytesIO(base64.b64decode(r["image_data"])))
    w, h = img.size; max_dim = 1280
    if w > max_dim or h > max_dim:
        nw, nh = (max_dim, int(h * max_dim / w)) if w > h else (int(w * max_dim / h), max_dim)
        img = img.resize((nw, nh), PILImage.Resampling.LANCZOS)
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    buf = BytesIO(); img.save(buf, format="JPEG", quality=85, optimize=True)
    data = buf.getvalue()
    if len(data) > 900_000:
        buf = BytesIO(); img.save(buf, format="JPEG", quality=70, optimize=True)
        data = buf.getvalue()
    return Image(data=data, format="jpeg")


def create_server() -> FastMCP:
    mcp = FastMCP(name="computer-use-windows",
        instructions="Windows desktop control. Screenshot first, act, then verify.")

    # ─── SCREENSHOT ───
    @mcp.tool
    async def computer_screenshot() -> Image:
        """Capture full desktop screenshot."""
        return _screenshot_result(await _a.screenshot())

    @mcp.tool
    async def computer_screenshot_region(x: int, y: int, width: int, height: int) -> Image:
        """Capture a rectangular region of the screen."""
        return _screenshot_result(await _a.screenshot_region(x, y, width, height))

    @mcp.tool
    async def computer_screenshot_window(window_id: int) -> Image:
        """Capture a specific window by HWND."""
        return _screenshot_result(await _a.screenshot_window(window_id))

    @mcp.tool
    async def computer_get_screen_size() -> Dict[str, Any]:
        """Get screen dimensions."""
        return await _a.get_screen_size()

    @mcp.tool
    async def computer_get_cursor_position() -> Dict[str, Any]:
        """Get current mouse cursor position."""
        return await _a.get_cursor_position()

    # ─── MOUSE ───
    @mcp.tool
    async def computer_click(x: int, y: int, button: str = "left") -> Dict[str, Any]:
        """Click at (x, y). button: left|right|middle."""
        ax, ay = _actual(x, y)
        if button == "right": return await _a.right_click(ax, ay)
        if button == "middle": return await _a.middle_click(ax, ay)
        return await _a.left_click(ax, ay)

    @mcp.tool
    async def computer_double_click(x: int, y: int) -> Dict[str, Any]:
        """Double-click at (x, y)."""
        return await _a.double_click(*_actual(x, y))

    @mcp.tool
    async def computer_move(x: int, y: int) -> Dict[str, Any]:
        """Move cursor to (x, y)."""
        return await _a.move_cursor(*_actual(x, y))

    @mcp.tool
    async def computer_drag(start_x: int, start_y: int, end_x: int, end_y: int,
                            button: str = "left", duration: float = 0.5) -> Dict[str, Any]:
        """Drag from (start_x, start_y) to (end_x, end_y)."""
        ax1, ay1 = _actual(start_x, start_y); ax2, ay2 = _actual(end_x, end_y)
        await _a.move_cursor(ax1, ay1)
        return await _a.drag_to(ax2, ay2, button, duration)

    @mcp.tool
    async def computer_scroll(x: int, y: int, scroll_x: int = 0, scroll_y: int = 0) -> Dict[str, Any]:
        """Scroll at (x, y). scroll_x: horizontal, scroll_y: vertical."""
        ax, ay = _actual(x, y); await _a.move_cursor(ax, ay)
        return await _a.scroll(scroll_x, scroll_y)

    @mcp.tool
    async def computer_mouse_down(x: Optional[int] = None, y: Optional[int] = None,
                                   button: str = "left") -> Dict[str, Any]:
        """Press and hold mouse button."""
        ax, ay = (None, None) if x is None else _actual(x, y)
        return await _a.mouse_down(ax, ay, button)

    @mcp.tool
    async def computer_mouse_up(x: Optional[int] = None, y: Optional[int] = None,
                                 button: str = "left") -> Dict[str, Any]:
        """Release mouse button."""
        ax, ay = (None, None) if x is None else _actual(x, y)
        return await _a.mouse_up(ax, ay, button)

    # ─── KEYBOARD ───
    @mcp.tool
    async def computer_type(text: str) -> Dict[str, Any]:
        """Type text at current cursor position."""
        return await _a.type_text(text)

    @mcp.tool
    async def computer_press_key(key: str) -> Dict[str, Any]:
        """Press a single key (e.g., 'enter', 'tab', 'a')."""
        return await _a.press_key(key)

    @mcp.tool
    async def computer_hotkey(keys: List[str]) -> Dict[str, Any]:
        """Press key combination (e.g., ['ctrl', 'c'])."""
        return await _a.hotkey(keys)

    @mcp.tool
    async def computer_key_down(key: str) -> Dict[str, Any]:
        """Press and hold a key."""
        return await _a.key_down(key)

    @mcp.tool
    async def computer_key_up(key: str) -> Dict[str, Any]:
        """Release a held key."""
        return await _a.key_up(key)

    # ─── CLIPBOARD ───
    @mcp.tool
    async def computer_clipboard_get() -> Dict[str, Any]:
        """Get clipboard text content."""
        return await _a.copy_to_clipboard()

    @mcp.tool
    async def computer_clipboard_set(text: str) -> Dict[str, Any]:
        """Set clipboard text content."""
        return await _a.set_clipboard(text)

    # ─── SHELL ───
    @mcp.tool
    async def computer_run_command(command: str) -> Dict[str, Any]:
        """Execute a shell command. Returns stdout, stderr, returncode."""
        return await _a.run_command(command)

    # ─── WINDOW MANAGEMENT ───
    @mcp.tool
    async def computer_launch(app: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Launch an application."""
        return await _a.launch(app, args)

    @mcp.tool
    async def computer_get_current_window() -> Dict[str, Any]:
        """Get the currently focused window."""
        return await _a.get_current_window_id()

    @mcp.tool
    async def computer_get_app_windows(app: str) -> Dict[str, Any]:
        """Get all windows for an app by name."""
        return await _a.get_application_windows(app)

    @mcp.tool
    async def computer_list_windows() -> Dict[str, Any]:
        """List ALL visible windows with details."""
        return await _a.list_all_windows()

    @mcp.tool
    async def computer_resize_window(window_id: int, width: int, height: int) -> Dict[str, Any]:
        """Resize a window."""
        return await _a.resize_window(window_id, width, height)

    @mcp.tool
    async def computer_minimize_window(window_id: int) -> Dict[str, Any]:
        """Minimize a window."""
        return await _a.minimize_window(window_id)

    @mcp.tool
    async def computer_maximize_window(window_id: int) -> Dict[str, Any]:
        """Maximize a window."""
        return await _a.maximize_window(window_id)

    @mcp.tool
    async def computer_restore_window(window_id: int) -> Dict[str, Any]:
        """Restore a minimized/maximized window."""
        return await _a.restore_window(window_id)

    @mcp.tool
    async def computer_close_window(window_id: int) -> Dict[str, Any]:
        """Close a window."""
        return await _a.close_window(window_id)

    # ─── PROCESSES ───
    @mcp.tool
    async def computer_list_processes() -> Dict[str, Any]:
        """List all running processes."""
        return await _a.list_processes()

    @mcp.tool
    async def computer_kill_process(pid: int) -> Dict[str, Any]:
        """Kill a process by PID."""
        return await _a.kill_process(pid)

    # ─── REGISTRY ───
    @mcp.tool
    async def computer_registry_read(key_path: str, value_name: str = "") -> Dict[str, Any]:
        """Read a Windows registry value."""
        return await _a.registry_read(key_path, value_name)

    @mcp.tool
    async def computer_registry_write(key_path: str, value_name: str, value: str,
                                       reg_type: str = "REG_SZ") -> Dict[str, Any]:
        """Write a Windows registry value."""
        return await _a.registry_write(key_path, value_name, value, reg_type)

    # ─── SERVICES ───
    @mcp.tool
    async def computer_list_services() -> Dict[str, Any]:
        """List all Windows services."""
        return await _a.list_services()

    @mcp.tool
    async def computer_service_status(name: str) -> Dict[str, Any]:
        """Check service status."""
        return await _a.service_status(name)

    @mcp.tool
    async def computer_service_start(name: str) -> Dict[str, Any]:
        """Start a Windows service."""
        return await _a.service_start(name)

    @mcp.tool
    async def computer_service_stop(name: str) -> Dict[str, Any]:
        """Stop a Windows service."""
        return await _a.service_stop(name)

    @mcp.tool
    async def computer_service_restart(name: str) -> Dict[str, Any]:
        """Restart a Windows service."""
        return await _a.service_restart(name)

    # ─── SYSTEM INFO ───
    @mcp.tool
    async def computer_system_info() -> Dict[str, Any]:
        """Get system info: OS, CPU, RAM, disks."""
        return await _a.system_info()

    # ─── FILE PERMISSIONS ───
    @mcp.tool
    async def computer_get_file_permissions(path: str) -> Dict[str, Any]:
        """Get file permissions (mode, owner, ACL on Windows)."""
        return await _a.get_file_permissions(path)

    # ─── ACCESSIBILITY ───
    @mcp.tool
    async def computer_accessibility_tree() -> Dict[str, Any]:
        """Get accessibility tree for foreground window."""
        return await _acc.get_accessibility_tree()

    @mcp.tool
    async def computer_find_element(role: Optional[str] = None,
                                     title: Optional[str] = None) -> Dict[str, Any]:
        """Find a window/element by role or title."""
        return await _acc.find_element(role=role, title=title)

    # ─── FILE SYSTEM ───
    @mcp.tool
    async def computer_file_read(path: str) -> Dict[str, Any]:
        """Read text content of a file."""
        return await _f.read_text(path)

    @mcp.tool
    async def computer_file_write(path: str, content: str) -> Dict[str, Any]:
        """Write text to a file (creates directories)."""
        return await _f.write_text(path, content)

    @mcp.tool
    async def computer_file_read_bytes(path: str, offset: int = 0,
                                        length: Optional[int] = None) -> Dict[str, Any]:
        """Read binary file (base64 encoded)."""
        return await _f.read_bytes(path, offset, length)

    @mcp.tool
    async def computer_file_write_bytes(path: str, content_base64: str) -> Dict[str, Any]:
        """Write binary content from base64 string."""
        return await _f.write_bytes(path, base64.b64decode(content_base64))

    @mcp.tool
    async def computer_file_exists(path: str) -> Dict[str, Any]:
        """Check if a file exists."""
        return await _f.file_exists(path)

    @mcp.tool
    async def computer_directory_exists(path: str) -> Dict[str, Any]:
        """Check if a directory exists."""
        return await _f.directory_exists(path)

    @mcp.tool
    async def computer_list_dir(path: str) -> Dict[str, Any]:
        """List directory contents."""
        return await _f.list_dir(path)

    @mcp.tool
    async def computer_create_dir(path: str) -> Dict[str, Any]:
        """Create a directory (recursive)."""
        return await _f.create_dir(path)

    @mcp.tool
    async def computer_delete_file(path: str) -> Dict[str, Any]:
        """Delete a file."""
        return await _f.delete_file(path)

    @mcp.tool
    async def computer_delete_dir(path: str) -> Dict[str, Any]:
        """Delete a directory recursively."""
        return await _f.delete_dir(path)

    @mcp.tool
    async def computer_get_file_size(path: str) -> Dict[str, Any]:
        """Get file size in bytes."""
        return await _f.get_file_size(path)

    @mcp.tool
    async def computer_move_file(src: str, dst: str) -> Dict[str, Any]:
        """Move/rename a file."""
        return await _f.move_file(src, dst)

    @mcp.tool
    async def computer_copy_file(src: str, dst: str) -> Dict[str, Any]:
        """Copy a file."""
        return await _f.copy_file(src, dst)

    return mcp


server = create_server()


async def main():
    logger.info("Starting computer-use-windows MCP server (stdio)...")
    await server.run_stdio_async()

if __name__ == "__main__":
    import anyio; anyio.run(main)
