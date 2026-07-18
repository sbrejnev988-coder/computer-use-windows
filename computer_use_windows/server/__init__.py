"""FastMCP server — Windows desktop control via Model Context Protocol.

v2.1.0 — CISA Audit Round 2 fixes:
  P0#1: screenshot → ToolResult (not Image with _meta)
  P0#2: computer_scroll → move_cursor + scroll(scroll_x, scroll_y)
  P0#3: computer_drag → move to start THEN drag
  P0#4: Frame validation — desktop_hash for all, registry not last_frame
  P0#5: CLI remote — pass args directly, don't re-parse
  P0#6: capability policy → fail-closed + require_capability decorator
  P0#7: PathPolicy — allowed roots, resolve, symlink check
  P1: fastmcp>=2.13.1 pinned
"""

import asyncio, base64, functools, hashlib, logging, os, sys, time, uuid
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from fastmcp.tools.tool import ToolResult

from ..handlers import (
    WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler,
    WindowsSystemHandler,
)

logger = logging.getLogger(__name__)

# ─── FastMCP version guard ─────────────────────────────────────────────────

_MIN_FASTMCP = (2, 13, 1)
try:
    from fastmcp import __version__ as _fmcp_ver
    _fmcp_tuple = tuple(int(x) for x in _fmcp_ver.split(".")[:3])
    if _fmcp_tuple < _MIN_FASTMCP:
        logger.warning(
            f"FastMCP {_fmcp_ver} < {'.'.join(map(str,_MIN_FASTMCP))}. "
            "Upgrade: pip install 'fastmcp>=2.13.1,<3'"
        )
except Exception:
    pass

# ─── Capability Profiles (P0#6: fail-closed) ─────────────────────────────

CAPABILITY_SCOPES = {
    "observe":              {"screenshot", "screenshot_region", "screenshot_window",
                              "get_screen_size", "get_cursor_position", "list_windows",
                              "get_current_window", "get_app_windows", "list_processes",
                              "system_info", "doctor"},

    "desktop.input":        {"click", "double_click", "right_click", "middle_click",
                              "move", "drag", "scroll", "mouse_down", "mouse_up",
                              "type", "press_key", "hotkey", "key_down", "key_up",
                              "clipboard_get", "clipboard_set"},

    "desktop.windows":      {"activate_window", "resize_window", "minimize_window",
                              "maximize_window", "restore_window", "close_window",
                              "launch"},

    "desktop.uia":          {"get_accessibility_tree", "find_element",
                              "get_ui_tree", "find_ui_elements", "focus_ui_element",
                              "invoke_ui_element", "set_ui_value", "toggle_ui_element",
                              "select_ui_element", "expand_ui_element",
                              "scroll_ui_element_into_view", "wait_for_ui_element"},

    "files.read":           {"file_read", "file_read_bytes", "file_exists",
                              "directory_exists", "list_dir", "get_file_size",
                              "get_file_permissions"},

    "files.write":          {"file_write", "file_write_bytes", "create_dir",
                              "move_file", "copy_file"},

    "files.delete":         {"delete_file", "delete_dir"},

    "admin.shell":          {"run_command"},

    "admin.processes":      {"kill_process"},

    "admin.registry":       {"registry_read", "registry_write"},

    "admin.services":       {"list_services", "service_status", "service_start",
                              "service_stop", "service_restart"},
}

PROFILES = {
    "observe": list(CAPABILITY_SCOPES["observe"]),

    "desktop": (
        CAPABILITY_SCOPES["observe"] |
        CAPABILITY_SCOPES["desktop.input"] |
        CAPABILITY_SCOPES["desktop.windows"] |
        CAPABILITY_SCOPES["desktop.uia"] |
        CAPABILITY_SCOPES["files.read"] |
        CAPABILITY_SCOPES["files.write"]
    ),

    "files": (
        CAPABILITY_SCOPES["observe"] |
        CAPABILITY_SCOPES["files.read"] |
        CAPABILITY_SCOPES["files.write"]
    ),

    "admin": (
        CAPABILITY_SCOPES["observe"] |
        CAPABILITY_SCOPES["desktop.input"] |
        CAPABILITY_SCOPES["desktop.windows"] |
        CAPABILITY_SCOPES["desktop.uia"] |
        CAPABILITY_SCOPES["files.read"] |
        CAPABILITY_SCOPES["files.write"] |
        CAPABILITY_SCOPES["files.delete"] |
        CAPABILITY_SCOPES["admin.shell"] |
        CAPABILITY_SCOPES["admin.processes"] |
        CAPABILITY_SCOPES["admin.registry"] |
        CAPABILITY_SCOPES["admin.services"]
    ),

    "unsafe": set(),  # empty = all allowed (checked specially)
}

ACTIVE_PROFILE = os.getenv("COMPUTER_USE_WINDOWS_PROFILE", "desktop")

# P0#6: FAIL-CLOSED — unknown profile = RuntimeError, not full access
if ACTIVE_PROFILE not in PROFILES:
    _valid = ", ".join(sorted(PROFILES.keys()))
    raise RuntimeError(
        f"Unknown COMPUTER_USE_WINDOWS_PROFILE='{ACTIVE_PROFILE}'. "
        f"Valid profiles: {_valid}"
    )

ALLOWED_CAPABILITIES = PROFILES[ACTIVE_PROFILE]
# 'unsafe' means ALL allowed
_IS_UNSAFE = (ACTIVE_PROFILE == "unsafe")


def _tool_has_capability(tool_name: str) -> bool:
    """Check if tool is allowed under active profile (fail-closed)."""
    if _IS_UNSAFE:
        return True
    return tool_name in ALLOWED_CAPABILITIES


def require_capability(tool_name: str):
    """Decorator: enforce capability check on any tool function."""
    def decorator(fn: Callable):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not _tool_has_capability(tool_name):
                return {
                    "success": False,
                    "error": f"Capability '{tool_name}' requires profile with sufficient scope. "
                             f"Current profile: '{ACTIVE_PROFILE}'"
                }
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


# ─── PathPolicy (P0#7): allowed-directory resolver ────────────────────────

class PathPolicy:
    """File path resolver with allowlist, normalization, symlink check."""

    def __init__(self, roots: Optional[List[str]] = None):
        env_roots = os.getenv("COMPUTER_USE_WINDOWS_ALLOWED_ROOTS", "")
        if roots is None and env_roots:
            roots = [r.strip() for r in env_roots.split(os.pathsep) if r.strip()]
        if not roots:
            # Default: user profile + temp
            roots = [
                os.path.expanduser("~"),
                os.environ.get("TEMP", os.environ.get("TMP", "C:\\Windows\\Temp")),
            ]
        self.roots: List[Path] = [Path(r).expanduser().resolve() for r in roots]

    def resolve(self, value: str) -> Path:
        """Resolve path and verify it's within allowed roots."""
        path = Path(value).expanduser().resolve()

        # Block dangerous prefixes
        blocked_prefixes = ("\\\\?\\", "\\\\.\\", "\\\\server\\", "\\\\")
        path_str = str(path)
        for prefix in blocked_prefixes:
            if path_str.startswith(prefix):
                raise PermissionError(f"Blocked path prefix: {prefix}")

        if not any(
            path == root or str(path).startswith(str(root) + os.sep)
            for root in self.roots
        ):
            raise PermissionError(
                f"Path '{path}' is outside allowed roots: "
                f"{[str(r) for r in self.roots]}"
            )
        return path

_path_policy = PathPolicy()


# ─── Frame: coordinate transformation (P0#4: desktop_hash for all) ────────

def _desktop_geometry_hash() -> str:
    """Hash of virtual desktop geometry — stable across screenshots."""
    if sys.platform != "win32":
        return "non-windows"
    from ..handlers.windows import _current_frame_hash
    return _current_frame_hash()


# P0#4: frame registry instead of just session.last_frame
_frame_registry: Dict[str, "Frame"] = {}

@dataclass(frozen=True)
class Frame:
    """Immutable frame: capture metadata + coordinate mapping."""

    frame_id: str
    capture_kind: Literal["desktop", "region", "window"]
    desktop_hash: str
    window_id: Optional[int]

    left: int
    top: int
    source_width: int
    source_height: int
    image_width: int
    image_height: int

    def to_screen(self, x: int, y: int) -> Tuple[int, int]:
        sx = self.left + round(x * self.source_width / self.image_width)
        sy = self.top + round(y * self.source_height / self.image_height)
        return sx, sy

    def validate(self) -> bool:
        """Check frame hasn't expired."""
        current_hash = _desktop_geometry_hash()
        if self.desktop_hash != current_hash:
            return False
        if self.capture_kind == "window" and self.window_id is not None:
            if sys.platform == "win32":
                try:
                    import win32gui
                    if not win32gui.IsWindow(self.window_id):
                        return False
                    # Check window still in same position
                    rect = win32gui.GetWindowRect(self.window_id)
                    if (
                        rect[0] != self.left or rect[1] != self.top or
                        rect[2] - rect[0] != self.source_width or
                        rect[3] - rect[1] != self.source_height
                    ):
                        return False
                except Exception:
                    return False
        return True


MAX_IMAGE_DIM = 1280  # Max dimension sent to model


def _make_frame(screenshot: Dict[str, Any], image: PILImage.Image,
                capture_kind: str, window_id: Optional[int] = None) -> Frame:
    """Construct a Frame from screenshot result + scaled PIL image."""
    left = screenshot.get("left", 0)
    top = screenshot.get("top", 0)
    src_w = screenshot.get("width", image.width)
    src_h = screenshot.get("height", image.height)
    img_w, img_h = image.size
    desktop_hash = _desktop_geometry_hash()
    frame_id = f"frm_{uuid.uuid4().hex[:8]}:{desktop_hash}"
    frame = Frame(
        frame_id=frame_id,
        capture_kind=capture_kind,
        desktop_hash=desktop_hash,
        window_id=window_id,
        left=left, top=top,
        source_width=src_w, source_height=src_h,
        image_width=img_w, image_height=img_h,
    )
    _frame_registry[frame_id] = frame
    return frame


def _scale_screenshot(screenshot: Dict[str, Any]) -> Tuple[Optional[PILImage.Image], Optional[Frame]]:
    """Process screenshot: validate, scale, build Frame. None on failure."""
    if not screenshot.get("success", True):
        return None, None
    image_data = screenshot.get("image_data")
    if not image_data:
        return None, None
    img = PILImage.open(BytesIO(base64.b64decode(image_data)))
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
    return img, None  # Frame built by caller with capture_kind


# ─── P0#1: Screenshot → ToolResult (not Image with _meta) ─────────────────

def _screenshot_to_result(
    screenshot: Dict[str, Any],
    capture_kind: Literal["desktop", "region", "window"],
    window_id: Optional[int] = None,
) -> ToolResult:
    """Convert screenshot dict to ToolResult with frame metadata."""
    img, _ = _scale_screenshot(screenshot)
    if img is None:
        raise RuntimeError(
            screenshot.get("error") or screenshot.get("message") or "Screenshot failed"
        )

    frame = _make_frame(screenshot, img, capture_kind, window_id)

    buf = BytesIO()
    img.save(buf, format="PNG")

    image_content = Image(
        data=buf.getvalue(),
        format="png",
    ).to_image_content()

    return ToolResult(
        content=[image_content],
        meta={
            "frame_id": frame.frame_id,
            "capture_kind": frame.capture_kind,
            "left": frame.left,
            "top": frame.top,
            "source_width": frame.source_width,
            "source_height": frame.source_height,
            "image_width": frame.image_width,
            "image_height": frame.image_height,
        },
    )


# ─── Coordinate resolution (frame_id → physical) ──────────────────────────

def _resolve_coords(
    x: int, y: int,
    frame_id: Optional[str] = None,
) -> Tuple[int, int]:
    """Convert image coordinates to physical screen coordinates."""
    if frame_id is None:
        return x, y  # Legacy: no frame, assume 1:1

    frame = _frame_registry.get(frame_id)
    if frame is None:
        raise RuntimeError(
            f"Unknown frame_id '{frame_id}'. Take a new screenshot first."
        )
    if not frame.validate():
        # Remove stale frame
        _frame_registry.pop(frame_id, None)
        raise RuntimeError(
            f"Frame '{frame_id}' expired — desktop/window geometry changed. Re-screenshot."
        )
    return frame.to_screen(x, y)


# ─── FastMCP Server Factory ────────────────────────────────────────────────

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
        version="2.1.0",
    )

    _input_lock = asyncio.Lock()

    # ═══════════ Observation ═══════════════════════════════════════════════

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("screenshot")
    async def computer_screenshot() -> ToolResult:
        result = await a.screenshot()
        return _screenshot_to_result(result, "desktop")

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("screenshot_region")
    async def computer_screenshot_region(
        x: int, y: int, width: int, height: int
    ) -> ToolResult:
        result = await a.screenshot_region(x, y, width, height)
        return _screenshot_to_result(result, "region")

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("screenshot_window")
    async def computer_screenshot_window(
        window_id: int
    ) -> ToolResult:
        result = await a.screenshot_window(window_id)
        return _screenshot_to_result(result, "window", window_id=window_id)

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("get_screen_size")
    async def computer_get_screen_size() -> Dict[str, Any]:
        return await a.get_screen_size()

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("get_cursor_position")
    async def computer_get_cursor_position() -> Dict[str, Any]:
        return await a.get_cursor_position()

    # ═══════════ Mouse ═════════════════════════════════════════════════════

    @mcp.tool(destructiveHint=True)
    @require_capability("click")
    async def computer_click(
        x: int, y: int, button: str = "left",
        frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            if button == "left":
                return await a.left_click(sx, sy)
            elif button == "right":
                return await a.right_click(sx, sy)
            else:
                return await a.middle_click(sx, sy)

    @mcp.tool(destructiveHint=True)
    @require_capability("double_click")
    async def computer_double_click(
        x: int, y: int, frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            return await a.double_click(sx, sy)

    @mcp.tool(destructiveHint=True)
    @require_capability("move")
    async def computer_move(
        x: int, y: int, frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            return await a.move_cursor(sx, sy)

    @mcp.tool(destructiveHint=True)
    @require_capability("drag")
    async def computer_drag(
        start_x: int, start_y: int,
        end_x: int, end_y: int,
        button: str = "left", duration: float = 0.5,
        frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        s_start_x, s_start_y = _resolve_coords(start_x, start_y, frame_id)
        s_end_x, s_end_y = _resolve_coords(end_x, end_y, frame_id)
        async with _input_lock:
            # P0#3: move to start BEFORE drag
            await a.move_cursor(s_start_x, s_start_y)
            return await a.drag_to(s_end_x, s_end_y, button, duration)

    @mcp.tool(destructiveHint=True)
    @require_capability("scroll")
    async def computer_scroll(
        x: int, y: int,
        scroll_x: int = 0, scroll_y: int = 0,
        frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            # P0#2: move cursor FIRST, then scroll(scroll_x, scroll_y) — 2 args, not 4
            await a.move_cursor(sx, sy)
            return await a.scroll(scroll_x, scroll_y)

    @mcp.tool(destructiveHint=True)
    @require_capability("mouse_down")
    async def computer_mouse_down(
        x: Optional[int] = None, y: Optional[int] = None,
        button: str = "left", frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = (x or 0, y or 0)
        if x is not None and y is not None:
            sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            return await a.mouse_down(sx, sy, button)

    @mcp.tool(destructiveHint=True)
    @require_capability("mouse_up")
    async def computer_mouse_up(
        x: Optional[int] = None, y: Optional[int] = None,
        button: str = "left", frame_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        sx, sy = (x or 0, y or 0)
        if x is not None and y is not None:
            sx, sy = _resolve_coords(x, y, frame_id)
        async with _input_lock:
            return await a.mouse_up(sx, sy, button)

    # ═══════════ Keyboard ══════════════════════════════════════════════════

    @mcp.tool(destructiveHint=True)
    @require_capability("type")
    async def computer_type(text: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.type_text(text)

    @mcp.tool(destructiveHint=True)
    @require_capability("press_key")
    async def computer_press_key(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.press_key(key)

    @mcp.tool(destructiveHint=True)
    @require_capability("hotkey")
    async def computer_hotkey(keys: List[str]) -> Dict[str, Any]:
        async with _input_lock:
            return await a.hotkey(keys)

    @mcp.tool(destructiveHint=True)
    @require_capability("key_down")
    async def computer_key_down(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.key_down(key)

    @mcp.tool(destructiveHint=True)
    @require_capability("key_up")
    async def computer_key_up(key: str) -> Dict[str, Any]:
        async with _input_lock:
            return await a.key_up(key)

    # ═══════════ Clipboard ════════════════════════════════════════════════

    @mcp.tool(readOnlyHint=True)
    @require_capability("clipboard_get")
    async def computer_clipboard_get() -> Dict[str, Any]:
        return await a.copy_to_clipboard()

    @mcp.tool(destructiveHint=True)
    @require_capability("clipboard_set")
    async def computer_clipboard_set(text: str) -> Dict[str, Any]:
        return await a.set_clipboard(text)

    # ═══════════ Shell & Launch ═══════════════════════════════════════════

    @mcp.tool(destructiveHint=True)
    @require_capability("run_command")
    async def computer_run_command(command: str) -> Dict[str, Any]:
        return await a.run_command(command)

    @mcp.tool(destructiveHint=True)
    @require_capability("launch")
    async def computer_launch(
        app: str, args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        return await a.launch(app, args)

    # ═══════════ Window Management ════════════════════════════════════════

    @mcp.tool(readOnlyHint=True)
    @require_capability("get_current_window")
    async def computer_get_current_window() -> Dict[str, Any]:
        return await a.get_current_window_id()

    @mcp.tool(readOnlyHint=True)
    @require_capability("get_app_windows")
    async def computer_get_app_windows(app: str) -> Dict[str, Any]:
        return await a.get_application_windows(app)

    @mcp.tool(readOnlyHint=True)
    @require_capability("list_windows")
    async def computer_list_windows() -> Dict[str, Any]:
        return await a.list_all_windows()

    @mcp.tool(destructiveHint=True)
    @require_capability("resize_window")
    async def computer_resize_window(window_id: int, width: int, height: int) -> Dict[str, Any]:
        return await a.resize_window(window_id, width, height)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    @require_capability("minimize_window")
    async def computer_minimize_window(window_id: int) -> Dict[str, Any]:
        return await a.minimize_window(window_id)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    @require_capability("maximize_window")
    async def computer_maximize_window(window_id: int) -> Dict[str, Any]:
        return await a.maximize_window(window_id)

    @mcp.tool(destructiveHint=True, idempotentHint=True)
    @require_capability("restore_window")
    async def computer_restore_window(window_id: int) -> Dict[str, Any]:
        return await a.restore_window(window_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("close_window")
    async def computer_close_window(window_id: int) -> Dict[str, Any]:
        return await a.close_window(window_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("activate_window")
    async def computer_activate_window(window_id: int) -> Dict[str, Any]:
        return await a.activate_window(window_id)

    # ═══════════ Processes, Registry, Services ════════════════════════════

    @mcp.tool(readOnlyHint=True)
    @require_capability("list_processes")
    async def computer_list_processes() -> Dict[str, Any]:
        return await a.list_processes()

    @mcp.tool(destructiveHint=True)
    @require_capability("kill_process")
    async def computer_kill_process(pid: int) -> Dict[str, Any]:
        return await a.kill_process(pid)

    @mcp.tool(readOnlyHint=True)
    @require_capability("registry_read")
    async def computer_registry_read(key_path: str, value_name: str = "") -> Dict[str, Any]:
        return await a.registry_read(key_path, value_name)

    @mcp.tool(destructiveHint=True)
    @require_capability("registry_write")
    async def computer_registry_write(
        key_path: str, value_name: str, value: str, reg_type: str = "REG_SZ"
    ) -> Dict[str, Any]:
        return await a.registry_write(key_path, value_name, value, reg_type)

    @mcp.tool(readOnlyHint=True)
    @require_capability("list_services")
    async def computer_list_services() -> Dict[str, Any]:
        return await a.list_services()

    @mcp.tool(readOnlyHint=True)
    @require_capability("service_status")
    async def computer_service_status(name: str) -> Dict[str, Any]:
        return await a.service_status(name)

    @mcp.tool(destructiveHint=True)
    @require_capability("service_start")
    async def computer_service_start(name: str) -> Dict[str, Any]:
        return await a.service_start(name)

    @mcp.tool(destructiveHint=True)
    @require_capability("service_stop")
    async def computer_service_stop(name: str) -> Dict[str, Any]:
        return await a.service_stop(name)

    @mcp.tool(destructiveHint=True)
    @require_capability("service_restart")
    async def computer_service_restart(name: str) -> Dict[str, Any]:
        return await a.service_restart(name)

    @mcp.tool(readOnlyHint=True)
    @require_capability("system_info")
    async def computer_system_info() -> Dict[str, Any]:
        return await a.system_info()

    @mcp.tool(readOnlyHint=True)
    @require_capability("get_file_permissions")
    async def computer_get_file_permissions(path: str) -> Dict[str, Any]:
        return await a.get_file_permissions(path)

    # ═══════════ Accessibility / UI Automation ═════════════════════════════

    @mcp.tool(readOnlyHint=True)
    @require_capability("get_accessibility_tree")
    async def computer_accessibility_tree() -> Dict[str, Any]:
        return await acc.get_accessibility_tree()

    @mcp.tool(readOnlyHint=True)
    @require_capability("find_element")
    async def computer_find_element(
        role: Optional[str] = None, title: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await acc.find_element(role, title)

    @mcp.tool(readOnlyHint=True)
    @require_capability("get_ui_tree")
    async def computer_get_ui_tree(max_depth: int = 5) -> Dict[str, Any]:
        return await acc.get_ui_tree(max_depth)

    @mcp.tool(readOnlyHint=True)
    @require_capability("find_ui_elements")
    async def computer_find_ui_elements(
        control_type: Optional[str] = None,
        name: Optional[str] = None,
        automation_id: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await acc.find_ui_elements(control_type, name, automation_id, class_name)

    @mcp.tool(destructiveHint=True)
    @require_capability("focus_ui_element")
    async def computer_focus_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.focus_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("invoke_ui_element")
    async def computer_invoke_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.invoke_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("set_ui_value")
    async def computer_set_ui_value(element_id: str, value: str) -> Dict[str, Any]:
        return await acc.set_ui_value(element_id, value)

    @mcp.tool(destructiveHint=True)
    @require_capability("toggle_ui_element")
    async def computer_toggle_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.toggle_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("select_ui_element")
    async def computer_select_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.select_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("expand_ui_element")
    async def computer_expand_ui_element(element_id: str) -> Dict[str, Any]:
        return await acc.expand_ui_element(element_id)

    @mcp.tool(destructiveHint=True)
    @require_capability("scroll_ui_element_into_view")
    async def computer_scroll_ui_element_into_view(element_id: str) -> Dict[str, Any]:
        return await acc.scroll_ui_element_into_view(element_id)

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("wait_for_ui_element")
    async def computer_wait_for_ui_element(
        control_type: Optional[str] = None,
        name: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]:
        return await acc.wait_for_ui_element(control_type, name, timeout_ms)

    # ═══════════ File Operations (PathPolicy enforced) ════════════════════

    @mcp.tool(readOnlyHint=True)
    @require_capability("file_read")
    async def computer_file_read(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.read_text(str(safe))

    @mcp.tool(destructiveHint=True)
    @require_capability("file_write")
    async def computer_file_write(path: str, content: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.write_text(str(safe), content)

    @mcp.tool(readOnlyHint=True)
    @require_capability("file_read_bytes")
    async def computer_file_read_bytes(
        path: str, offset: int = 0, length: Optional[int] = None
    ) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.read_bytes(str(safe), offset, length)

    @mcp.tool(destructiveHint=True)
    @require_capability("file_write_bytes")
    async def computer_file_write_bytes(path: str, content_base64: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.write_bytes(str(safe), base64.b64decode(content_base64))

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("file_exists")
    async def computer_file_exists(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.file_exists(str(safe))

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("directory_exists")
    async def computer_directory_exists(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.directory_exists(str(safe))

    @mcp.tool(readOnlyHint=True)
    @require_capability("list_dir")
    async def computer_list_dir(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.list_dir(str(safe))

    @mcp.tool(destructiveHint=True)
    @require_capability("create_dir")
    async def computer_create_dir(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.create_dir(str(safe))

    @mcp.tool(destructiveHint=True)
    @require_capability("delete_file")
    async def computer_delete_file(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.delete_file(str(safe))

    @mcp.tool(destructiveHint=True)
    @require_capability("delete_dir")
    async def computer_delete_dir(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.delete_dir(str(safe))

    @mcp.tool(readOnlyHint=True, idempotentHint=True)
    @require_capability("get_file_size")
    async def computer_get_file_size(path: str) -> Dict[str, Any]:
        safe = _path_policy.resolve(path)
        return await f.get_file_size(str(safe))

    @mcp.tool(destructiveHint=True)
    @require_capability("move_file")
    async def computer_move_file(src: str, dst: str) -> Dict[str, Any]:
        safe_src = _path_policy.resolve(src)
        safe_dst = _path_policy.resolve(dst)
        return await f.move_file(str(safe_src), str(safe_dst))

    @mcp.tool(destructiveHint=True)
    @require_capability("copy_file")
    async def computer_copy_file(src: str, dst: str) -> Dict[str, Any]:
        safe_src = _path_policy.resolve(src)
        safe_dst = _path_policy.resolve(dst)
        return await f.copy_file(str(safe_src), str(safe_dst))

    _server = mcp
    return mcp


# ─── Entry Points ──────────────────────────────────────────────────────────

def enable_dpi_awareness() -> None:
    """Enable Per-Monitor DPI Awareness V2."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
        ok = user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        if not ok:
            raise ctypes.WinError()
        logger.info("DPI: Per-Monitor V2 enabled")
    except Exception as e:
        logger.warning(f"DPI awareness failed: {e}")


async def _serve() -> None:
    server = create_server()
    await server.run_stdio_async()


def main() -> None:
    """Synchronous entry point for console script."""
    import anyio
    enable_dpi_awareness()
    anyio.run(_serve)
