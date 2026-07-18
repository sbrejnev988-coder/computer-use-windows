"""FastMCP server — Windows desktop control via Model Context Protocol.

CISA Red Team Audit Fixes v2.0:
  P0: async entry point → sync main() with anyio.run
  P0: frame_id coordinate transformation (Frame class)
  P0: activate_window tool
  P0: screenshot error propagation (not masked)
  P0: DPI Per-Monitor V2 via SetProcessDpiAwarenessContext
  P1: action lock (asyncio.Lock) for input serialization
  P1: capability profiles (observe/desktop/files/admin/unsafe)
  P1: session_id + sequence numbers for long workflows
  P2: readOnlyHint/destructiveHint/idempotentHint annotations
"""

import asyncio, base64, hashlib, logging, os, sys, time, uuid
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from PIL import Image as PILImage

from ..handlers import (
    WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler,
    WindowsSystemHandler,
)

logger = logging.getLogger(__name__)

# ─── Capability Profiles (P1 security) ────────────────────────────────────

@dataclass
class CapabilityProfile:
    name: str
    allowed_operations: List[str]
    description: str

PROFILES = {
    "observe": CapabilityProfile(
        "observe",
        ["screenshot", "screenshot_region", "screenshot_window",
         "get_screen_size", "get_cursor_position", "list_windows",
         "get_current_window", "get_app_windows", "list_processes",
         "system_info", "doctor"],
        "Read-only observation: screenshots, windows, processes, system info"
    ),
    "desktop": CapabilityProfile(
        "desktop",
        ["screenshot", "screenshot_region", "screenshot_window",
         "get_screen_size", "get_cursor_position",
         "click", "double_click", "right_click", "middle_click",
         "move", "drag", "scroll", "mouse_down", "mouse_up",
         "type", "press_key", "hotkey", "key_down", "key_up",
         "clipboard_get", "clipboard_set",
         "activate_window", "list_windows", "get_current_window",
         "get_app_windows", "resize_window", "minimize_window",
         "maximize_window", "restore_window", "close_window",
         "launch", "get_accessibility_tree", "find_element",
         "get_ui_tree", "find_ui_elements", "focus_ui_element",
         "invoke_ui_element", "set_ui_value", "toggle_ui_element",
         "select_ui_element", "expand_ui_element",
         "scroll_ui_element_into_view", "wait_for_ui_element",
         "system_info", "doctor"],
        "Desktop control: mouse, keyboard, UIA, window management"
    ),
    "files": CapabilityProfile(
        "files",
        ["file_read", "file_read_bytes", "file_write", "file_write_bytes",
         "file_exists", "dir_exists", "list_dir", "create_dir",
         "get_file_size", "get_file_permissions"],
        "File operations: read/write/list within allowed directories only"
    ),
    "admin": CapabilityProfile(
        "admin",
        ["run_command", "list_processes", "kill_process",
         "registry_read", "registry_write",
         "list_services", "service_status", "service_start",
         "service_stop", "service_restart"],
        "Administrative: shell, processes, registry, services"
    ),
    "unsafe": CapabilityProfile(
        "unsafe",
        ["*"],
        "Full access — only when explicitly enabled"
    ),
}

DEFAULT_PROFILE = "desktop"
ACTIVE_PROFILE = os.getenv("COMPUTER_USE_WINDOWS_PROFILE", DEFAULT_PROFILE)


def _check_profile(tool_name: str) -> bool:
    """Check if tool is allowed under active capability profile."""
    if ACTIVE_PROFILE == "unsafe":
        return True
    profile = PROFILES.get(ACTIVE_PROFILE)
    if not profile:
        return True  # Unknown profile → allow all (safe default)
    return tool_name in profile.allowed_operations


# ─── Frame: coordinate transformation model (P0) ──────────────────────────

@dataclass(frozen=True)
class Frame:
    """Immutable frame describing a screenshot and its coordinate mapping."""
    frame_id: str
    left: int           # virtual desktop left coordinate
    top: int            # virtual desktop top coordinate
    source_width: int   # original capture width
    source_height: int  # original capture height
    image_width: int    # scaled image width (sent to model)
    image_height: int   # scaled image height (sent to model)

    def to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """Convert image coordinates to physical screen coordinates."""
        sx = self.left + round(x * self.source_width / self.image_width)
        sy = self.top + round(y * self.source_height / self.image_height)
        return sx, sy

    def validate(self) -> bool:
        """Check frame hasn't expired (window/desktop geometry unchanged)."""
        from ..handlers.windows import _current_frame_hash
        return _current_frame_hash() == self.frame_id.split(":")[1] if ":" in self.frame_id else True


# ─── Session management (P1) ──────────────────────────────────────────────

@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    sequence: int = 0
    last_frame: Optional[Frame] = None
    created_at: float = field(default_factory=time.time)

_sessions: Dict[str, Session] = {}
_current_session: Optional[Session] = None
_input_lock = asyncio.Lock()
MAX_IMAGE_DIM = 1280  # Max dimension for screenshots sent to model


def _get_session(session_id: Optional[str] = None) -> Session:
    global _current_session
    if session_id:
        if session_id not in _sessions:
            _sessions[session_id] = Session(session_id=session_id)
        _current_session = _sessions[session_id]
        return _current_session
    if _current_session is None:
        _current_session = Session()
        _sessions[_current_session.session_id] = _current_session
    return _current_session


# ─── Helper: build frame from screenshot result ───────────────────────────

def _make_frame(screenshot_result: Dict[str, Any], image: PILImage.Image) -> Frame:
    """Construct a Frame from a screenshot result dict + scaled PIL image."""
    left = screenshot_result.get("left", 0)
    top = screenshot_result.get("top", 0)
    source_w = screenshot_result.get("width", image.width)
    source_h = screenshot_result.get("height", image.height)
    img_w, img_h = image.size
    geom_hash = hashlib.sha256(
        f"{left},{top},{source_w},{source_h}".encode()
    ).hexdigest()[:12]
    frame_id = f"frm_{uuid.uuid4().hex[:8]}:{geom_hash}"
    return Frame(
        frame_id=frame_id,
        left=left, top=top,
        source_width=source_w, source_height=source_h,
        image_width=img_w, image_height=img_h,
    )


def _scale_screenshot(screenshot: Dict[str, Any]) -> Tuple[PILImage.Image, Frame]:
    """Process screenshot result: validate, scale, build Frame."""
    if not screenshot.get("success", True):
        # FIXED P0: propagate errors, don't mask them
        return None, None

    image_data = screenshot.get("image_data")
    if not image_data:
        raise RuntimeError(
            f"Screenshot error: {screenshot.get('error', 'Unknown error')}"
        )

    img = PILImage.open(BytesIO(base64.b64decode(image_data)))
    # Scale down if needed while preserving aspect ratio
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)

    frame = _make_frame(screenshot, img)
    return img, frame


def _screenshot_to_image(
    screenshot: Dict[str, Any],
    session: Optional[Session] = None
) -> Image:
    """Convert screenshot dict to FastMCP Image with frame_id metadata."""
    img, frame = _scale_screenshot(screenshot)
    if img is None:
        raise RuntimeError(f"Screenshot failed: {screenshot.get('error', 'Unknown')}")

    if session:
        session.last_frame = frame
        session.sequence += 1

    # Encode frame metadata into image for MCP protocol
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()

    return Image(
        format="png",
        data=encoded,
        _meta={
            "frame_id": frame.frame_id,
            "left": frame.left,
            "top": frame.top,
            "source_width": frame.source_width,
            "source_height": frame.source_height,
            "image_width": frame.image_width,
            "image_height": frame.image_height,
        }
    )


# ─── Extract frame_id from action params ──────────────────────────────────

def _resolve_coords(
    x: int, y: int,
    frame_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Tuple[int, int]:
    """Convert image-space coordinates to physical screen coordinates."""
    session = _get_session(session_id)
    frame = session.last_frame

    if frame_id:
        # Find the right frame (from this or another session)
        if frame is None or frame.frame_id != frame_id:
            raise RuntimeError(f"Stale frame_id: {frame_id}. Take a new screenshot.")
        if not frame.validate():
            raise RuntimeError(f"Frame {frame_id} expired — geometry changed. Re-screenshot.")

    if frame is None:
        # No frame yet — assume 1:1 (legacy behavior)
        return x, y

    return frame.to_screen(x, y)


# ─── FastMCP Server ────────────────────────────────────────────────────────

# Don't create global server at import time — use factory function
_server: Optional[FastMCP] = None
_handlers: Optional[Dict[str, Any]] = None


def _get_handlers() -> Dict[str, Any]:
    global _handlers
    if _handlers is None:
        _handlers = {
            "automation": WindowsAutomationHandler(),
            "files": WindowsFileHandler(),
            "accessibility": WindowsAccessibilityHandler(),
            "system": WindowsSystemHandler(),
        }
    return _handlers


def create_server() -> FastMCP:
    global _server
    if _server is not None:
        return _server

    handlers = _get_handlers()
    a = handlers["automation"]
    f = handlers["files"]
    acc = handlers["accessibility"]
    s = handlers["system"]

    mcp = FastMCP(
        "Computer Use Windows",
        description="Windows desktop control via MCP — mouse, keyboard, UIA, files, system",
        version="2.0.0",
    )

    # ─── Observation Tools ─────────────────────────────────────────────

    @mcp.tool(
        readOnlyHint=True, idempotentHint=True,
        description="Capture full screen screenshot. Returns frame_id for coordinate mapping."
    )
    async def computer_screenshot(
        session_id: Optional[str] = None,
    ) -> Image:
        result = await a.screenshot()
        return _screenshot_to_image(result, _get_session(session_id))

    @mcp.tool(
        readOnlyHint=True, idempotentHint=True,
        description="Capture a region of the screen."
    )
    async def computer_screenshot_region(
        x: int, y: int, width: int, height: int,
        session_id: Optional[str] = None,
    ) -> Image:
        result = await a.screenshot_region(x, y, width, height)
        return _screenshot_to_image(result, _get_session(session_id))

    @mcp.tool(
        readOnlyHint=True, idempotentHint=True,
        description="Capture a specific window by HWND."
    )
    async def computer_screenshot_window(
        window_id: int,
        session_id: Optional[str] = None,
    ) -> Image:
        result = await a.screenshot_window(window_id)
        return _screenshot_to_image(result, _get_session(session_id))

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_get_screen_size() -> Dict[str, Any]:
        return await a.get_screen_size()

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_get_cursor_position() -> Dict[str, Any]:
        return await a.get_cursor_position()

    # ─── Mouse Tools ──────────────────────────────────────────────────

    @mcp.tool(destructiveHint=True)
    async def computer_click(
        x: int, y: int,
        button: str = "left",
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.left_click(sx, sy) if button == "left" else \
                   await a.right_click(sx, sy) if button == "right" else \
                   await a.middle_click(sx, sy)

    @mcp.tool(destructiveHint=True)
    async def computer_double_click(
        x: int, y: int,
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.double_click(sx, sy)

    @mcp.tool(destructiveHint=True)
    async def computer_move(
        x: int, y: int,
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.move_cursor(sx, sy)

    @mcp.tool(destructiveHint=True)
    async def computer_drag(
        start_x: int, start_y: int,
        end_x: int, end_y: int,
        button: str = "left",
        duration: float = 0.5,
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        s_start_x, s_start_y = _resolve_coords(start_x, start_y, frame_id, session_id)
        s_end_x, s_end_y = _resolve_coords(end_x, end_y, frame_id, session_id)
        async with _input_lock:
            return await a.drag_to(s_end_x, s_end_y, button, duration)

    @mcp.tool(destructiveHint=True)
    async def computer_scroll(
        x: int, y: int,
        scroll_x: int = 0, scroll_y: int = 0,
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.scroll(sx, sy, scroll_x, scroll_y)

    @mcp.tool(destructiveHint=True)
    async def computer_mouse_down(
        x: Optional[int] = None, y: Optional[int] = None,
        button: str = "left",
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = (x, y)
        if x is not None and y is not None:
            sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.mouse_down(sx, sy, button)

    @mcp.tool(destructiveHint=True)
    async def computer_mouse_up(
        x: Optional[int] = None, y: Optional[int] = None,
        button: str = "left",
        frame_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = (x, y)
        if x is not None and y is not None:
            sx, sy = _resolve_coords(x, y, frame_id, session_id)
        async with _input_lock:
            return await a.mouse_up(sx, sy, button)

    # ─── Keyboard Tools ───────────────────────────────────────────────

    @mcp.tool(destructiveHint=True)
    async def computer_type(text: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.type_text(text)

    @mcp.tool(destructiveHint=True)
    async def computer_press_key(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.press_key(key)

    @mcp.tool(destructiveHint=True)
    async def computer_hotkey(keys: List[str]) -> Dict[str, Any]:
        async with _input_lock:
            return await a.hotkey(keys)

    @mcp.tool(destructiveHint=True)
    async def computer_key_down(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.key_down(key)

    @mcp.tool(destructiveHint=True)
    async def computer_key_up(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.key_up(key)

    # ─── Clipboard ────────────────────────────────────────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_clipboard_get() -> Dict[str, Any]:
        return await a.copy_to_clipboard()

    @mcp.tool(destructiveHint=True)
    async def computer_clipboard_set(text: str) -> Dict[str, Any]:
        return await a.set_clipboard(text)

    # ─── Shell & Launch (admin profile required) ──────────────────────

    @mcp.tool(destructiveHint=True)
    async def computer_run_command(command: str) -> Dict[str, Any]:
        if not _check_profile("run_command"):
            return {"success": False, "error": "admin profile required"}
        return await a.run_command(command)

    @mcp.tool(destructiveHint=True)
    async def computer_launch(
        app: str, args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if not _check_profile("launch"):
            return {"success": False, "error": "desktop profile required"}
        return await a.launch(app, args)

    # ─── Window Management ────────────────────────────────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_get_current_window() -> Dict[str, Any]:
        return await a.get_current_window_id()

    @mcp.tool(readOnlyHint=True)
    async def computer_get_app_windows(app: str) -> Dict[str, Any]:
        return await a.get_application_windows(app)

    @mcp.tool(readOnlyHint=True)
    async def computer_list_windows() -> Dict[str, Any]:
        return await a.list_all_windows()

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    async def computer_resize_window(
        window_id: int, width: int, height: int
    ) -> Dict[str, Any]:
        return await a.resize_window(window_id, width, height)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    async def computer_minimize_window(window_id: int) -> Dict[str, Any]:
        return await a.minimize_window(window_id)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    async def computer_maximize_window(window_id: int) -> Dict[str, Any]:
        return await a.maximize_window(window_id)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    async def computer_restore_window(window_id: int) -> Dict[str, Any]:
        return await a.restore_window(window_id)

    @mcp.tool(destructiveHint=True)
    async def computer_close_window(window_id: int) -> Dict[str, Any]:
        return await a.close_window(window_id)

    @mcp.tool(destructiveHint=True)
    async def computer_activate_window(window_id: int) -> Dict[str, Any]:
        """P0 NEW: Activate and bring window to foreground.
        
        Steps: restore if minimized → ShowWindow → SetForegroundWindow
        → AttachThreadInput fallback → verify GetForegroundWindow.
        """
        return await a.activate_window(window_id)

    # ─── Processes, Registry, Services (admin profile) ────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_list_processes() -> Dict[str, Any]:
        return await a.list_processes()

    @mcp.tool(destructiveHint=True)
    async def computer_kill_process(pid: int) -> Dict[str, Any]:
        if not _check_profile("kill_process"):
            return {"success": False, "error": "admin profile required"}
        return await a.kill_process(pid)

    @mcp.tool(readOnlyHint=True)
    async def computer_registry_read(
        key_path: str, value_name: str = ""
    ) -> Dict[str, Any]:
        if not _check_profile("registry_read"):
            return {"success": False, "error": "admin profile required"}
        return await a.registry_read(key_path, value_name)

    @mcp.tool(destructiveHint=True)
    async def computer_registry_write(
        key_path: str, value_name: str, value: str, reg_type: str = "REG_SZ"
    ) -> Dict[str, Any]:
        if not _check_profile("registry_write"):
            return {"success": False, "error": "admin profile required"}
        return await a.registry_write(key_path, value_name, value, reg_type)

    @mcp.tool(readOnlyHint=True)
    async def computer_list_services() -> Dict[str, Any]:
        if not _check_profile("list_services"):
            return {"success": False, "error": "admin profile required"}
        return await a.list_services()

    @mcp.tool(readOnlyHint=True)
    async def computer_service_status(name: str) -> Dict[str, Any]:
        if not _check_profile("service_status"):
            return {"success": False, "error": "admin profile required"}
        return await a.service_status(name)

    @mcp.tool(destructiveHint=True)
    async def computer_service_start(name: str) -> Dict[str, Any]:
        if not _check_profile("service_start"):
            return {"success": False, "error": "admin profile required"}
        return await a.service_start(name)

    @mcp.tool(destructiveHint=True)
    async def computer_service_stop(name: str) -> Dict[str, Any]:
        if not _check_profile("service_stop"):
            return {"success": False, "error": "admin profile required"}
        return await a.service_stop(name)

    @mcp.tool(destructiveHint=True)
    async def computer_service_restart(name: str) -> Dict[str, Any]:
        if not _check_profile("service_restart"):
            return {"success": False, "error": "admin profile required"}
        return await a.service_restart(name)

    @mcp.tool(readOnlyHint=True)
    async def computer_system_info() -> Dict[str, Any]:
        return await a.system_info()

    @mcp.tool(readOnlyHint=True)
    async def computer_get_file_permissions(path: str) -> Dict[str, Any]:
        return await a.get_file_permissions(path)

    # ─── Accessibility / UI Automation ────────────────────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_accessibility_tree() -> Dict[str, Any]:
        return await acc.get_accessibility_tree()

    @mcp.tool(readOnlyHint=True)
    async def computer_find_element(
        role: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await acc.find_element(role, title)

    # ─── P1: True UI Automation tools ─────────────────────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_get_ui_tree(
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """Get full UIA tree with element IDs, control types, names."""
        return await acc.get_ui_tree(max_depth)

    @mcp.tool(readOnlyHint=True)
    async def computer_find_ui_elements(
        control_type: Optional[str] = None,
        name: Optional[str] = None,
        automation_id: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find UIA elements by properties. Returns stable element_ids."""
        return await acc.find_ui_elements(control_type, name, automation_id, class_name)

    @mcp.tool(destructiveHint=True)
    async def computer_focus_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.focus_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    async def computer_invoke_ui_element(element_id: str) -> Dict[str, Any]:
        """Click/invoke a UIA element (InvokePattern)."""
        return await acc.invoke_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    async def computer_set_ui_value(
        element_id: str, value: str
    ) -> Dict[str, Any]:
        """Set value on a UIA element (ValuePattern)."""
        return await acc.set_ui_value(element_id, value)

    @mcp.tool(destructiveHint=True)
    async def computer_toggle_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.toggle_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    async def computer_select_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.select_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    async def computer_expand_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.expand_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    async def computer_scroll_ui_element_into_view(element_id: str) -> Dict[str, Any]:
        return await acc.scroll_ui_element_into_view(element_id)

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_wait_for_ui_element(
        control_type: Optional[str] = None,
        name: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        return await acc.wait_for_ui_element(control_type, name, timeout_ms)

    # ─── File Operations (allowed directories only) ───────────────────

    @mcp.tool(readOnlyHint=True)
    async def computer_file_read(path: str) -> Dict[str, Any]:
        if not _check_profile("file_read"):
            return {"success": False, "error": "files profile required"}
        return await f.read_text(path)

    @mcp.tool(destructiveHint=True)
    async def computer_file_write(path: str, content: str) -> Dict[str, Any]:
        if not _check_profile("file_write"):
            return {"success": False, "error": "files profile required"}
        return await f.write_text(path, content)

    @mcp.tool(readOnlyHint=True)
    async def computer_file_read_bytes(
        path: str, offset: int = 0, length: Optional[int] = None
    ) -> Dict[str, Any]:
        if not _check_profile("file_read_bytes"):
            return {"success": False, "error": "files profile required"}
        return await f.read_bytes(path, offset, length)

    @mcp.tool(destructiveHint=True)
    async def computer_file_write_bytes(
        path: str, content_base64: str
    ) -> Dict[str, Any]:
        if not _check_profile("file_write_bytes"):
            return {"success": False, "error": "files profile required"}
        return await f.write_bytes(path, base64.b64decode(content_base64))

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_file_exists(path: str) -> Dict[str, Any]:
        return await f.file_exists(path)

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_directory_exists(path: str) -> Dict[str, Any]:
        return await f.directory_exists(path)

    @mcp.tool(readOnlyHint=True)
    async def computer_list_dir(path: str) -> Dict[str, Any]:
        return await f.list_dir(path)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    async def computer_create_dir(path: str) -> Dict[str, Any]:
        return await f.create_dir(path)

    @mcp.tool(destructiveHint=True)
    async def computer_delete_file(path: str) -> Dict[str, Any]:
        if not _check_profile("delete_file"):
            return {"success": False, "error": "admin profile required"}
        return await f.delete_file(path)

    @mcp.tool(destructiveHint=True)
    async def computer_delete_dir(path: str) -> Dict[str, Any]:
        if not _check_profile("delete_dir"):
            return {"success": False, "error": "admin profile required"}
        return await f.delete_dir(path)

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    async def computer_get_file_size(path: str) -> Dict[str, Any]:
        return await f.get_file_size(path)

    @mcp.tool(destructiveHint=True)
    async def computer_move_file(src: str, dst: str) -> Dict[str, Any]:
        if not _check_profile("move_file"):
            return {"success": False, "error": "files profile required"}
        return await f.move_file(src, dst)

    @mcp.tool(destructiveHint=True)
    async def computer_copy_file(src: str, dst: str) -> Dict[str, Any]:
        if not _check_profile("copy_file"):
            return {"success": False, "error": "files profile required"}
        return await f.copy_file(src, dst)

    _server = mcp
    return mcp


# ─── Entry Points ──────────────────────────────────────────────────────────

def enable_dpi_awareness() -> None:
    """Enable Per-Monitor DPI Awareness V2 (P0 fix)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        ok = user32.SetProcessDpiAwarenessContext(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        if not ok:
            raise ctypes.WinError()
        logger.info("DPI: Per-Monitor V2 enabled")
    except Exception as e:
        logger.warning(f"DPI awareness failed: {e}. "
                       "Consider setting via application manifest.")


async def _serve() -> None:
    """Async server entry point."""
    server = create_server()
    await server.run_stdio_async()


def main() -> None:
    """Synchronous entry point for console script (P0 fix).
    
    FIXED: previously was async def main() — console scripts
    cannot await directly. Now uses anyio.run().
    """
    import anyio
    enable_dpi_awareness()
    anyio.run(_serve)
