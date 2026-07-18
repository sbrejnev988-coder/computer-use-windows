"""Abstract base classes for platform-specific automation handlers.

CISA Audit v2.0 additions:
  - activate_window method
  - Frame-aware screenshot signatures
  - UI Automation (UIA) full interface
  - Scoped system operations (win32service, subprocess timeout)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class BaseAutomationHandler(ABC):
    """Mouse, keyboard, window management, processes, services."""

    @abstractmethod
    def is_desktop_locked(self) -> bool: ...

    # ── Screenshots ───────────────────────────────────────────────────

    @abstractmethod
    async def screenshot(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def screenshot_region(self, x: int, y: int, width: int, height: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def screenshot_window(self, window_id: Optional[int] = None) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_screen_size(self) -> Dict[str, int]: ...

    @abstractmethod
    async def get_cursor_position(self) -> Dict[str, int]: ...

    # ── Mouse ─────────────────────────────────────────────────────────

    @abstractmethod
    async def mouse_down(self, x=None, y=None, button="left") -> Dict[str, Any]: ...

    @abstractmethod
    async def mouse_up(self, x=None, y=None, button="left") -> Dict[str, Any]: ...

    @abstractmethod
    async def left_click(self, x=None, y=None) -> Dict[str, Any]: ...

    @abstractmethod
    async def right_click(self, x=None, y=None) -> Dict[str, Any]: ...

    @abstractmethod
    async def middle_click(self, x=None, y=None) -> Dict[str, Any]: ...

    @abstractmethod
    async def double_click(self, x=None, y=None) -> Dict[str, Any]: ...

    @abstractmethod
    async def move_cursor(self, x: int, y: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def drag_to(self, x: int, y: int, button="left", duration=0.5) -> Dict[str, Any]: ...

    @abstractmethod
    async def scroll(self, scroll_x: int, scroll_y: int) -> Dict[str, Any]: ...

    # ── Keyboard ──────────────────────────────────────────────────────

    @abstractmethod
    async def key_down(self, key: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def key_up(self, key: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def type_text(self, text: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def press_key(self, key: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def hotkey(self, keys: List[str]) -> Dict[str, Any]: ...

    # ── Clipboard ─────────────────────────────────────────────────────

    @abstractmethod
    async def copy_to_clipboard(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def set_clipboard(self, text: str) -> Dict[str, Any]: ...

    # ── Shell ─────────────────────────────────────────────────────────

    @abstractmethod
    async def run_command(self, command: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def launch(self, app: str, args: List[str] | None = None) -> Dict[str, Any]: ...

    # ── Windows ───────────────────────────────────────────────────────

    @abstractmethod
    async def get_current_window_id(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_application_windows(self, app: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def list_all_windows(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def resize_window(self, window_id: int, w: int, h: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def minimize_window(self, window_id: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def maximize_window(self, window_id: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def restore_window(self, window_id: int) -> Dict[str, Any]: ...

    @abstractmethod
    async def close_window(self, window_id: int) -> Dict[str, Any]: ...

    # ── P0 NEW: Window activation ────────────────────────────────────

    @abstractmethod
    async def activate_window(self, window_id: int) -> Dict[str, Any]:
        """Activate window: restore → ShowWindow → SetForegroundWindow → verify.

        Returns success with foreground_verified: bool.
        """
        ...

    # ── Processes ─────────────────────────────────────────────────────

    @abstractmethod
    async def list_processes(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def kill_process(self, pid: int) -> Dict[str, Any]: ...

    # ── Registry ──────────────────────────────────────────────────────

    @abstractmethod
    async def registry_read(self, key_path: str, value_name: str = "") -> Dict[str, Any]: ...

    @abstractmethod
    async def registry_write(self, key_path: str, value_name: str, value: str, reg_type: str = "REG_SZ") -> Dict[str, Any]: ...

    # ── Services ──────────────────────────────────────────────────────

    @abstractmethod
    async def list_services(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def service_status(self, name: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def service_start(self, name: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def service_stop(self, name: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def service_restart(self, name: str) -> Dict[str, Any]: ...

    # ── System ────────────────────────────────────────────────────────

    @abstractmethod
    async def system_info(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_file_permissions(self, path: str) -> Dict[str, Any]: ...


class BaseAccessibilityHandler(ABC):
    """UI Automation — real UIA tree, control patterns, element operations."""

    # Legacy compat (EnumChildWindows-based, deprecated in favor of UIA)
    @abstractmethod
    async def get_accessibility_tree(self) -> Dict[str, Any]: ...

    @abstractmethod
    async def find_element(self, role=None, title=None) -> Dict[str, Any]: ...

    # ── P1: True UI Automation ────────────────────────────────────────

    @abstractmethod
    async def get_ui_tree(self, max_depth: int = 5) -> Dict[str, Any]:
        """Get UIA tree with element IDs. Uses uiautomation library."""
        ...

    @abstractmethod
    async def find_ui_elements(
        self,
        control_type: Optional[str] = None,
        name: Optional[str] = None,
        automation_id: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find UIA elements. Returns stable element_ids for further actions."""
        ...

    @abstractmethod
    async def focus_ui_element(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def invoke_ui_element(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def set_ui_value(self, element_id: str, value: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def toggle_ui_element(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def select_ui_element(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def expand_ui_element(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def scroll_ui_element_into_view(self, element_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def wait_for_ui_element(
        self, control_type: Optional[str] = None,
        name: Optional[str] = None,
        timeout_ms: int = 5000,
    ) -> Dict[str, Any]: ...


class BaseFileHandler(ABC):
    """File system operations within allowed directories."""

    @abstractmethod
    async def read_text(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def write_text(self, path: str, content: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def read_bytes(self, path: str, offset: int = 0, length: Optional[int] = None) -> Dict[str, Any]: ...

    @abstractmethod
    async def write_bytes(self, path: str, content: bytes) -> Dict[str, Any]: ...

    @abstractmethod
    async def file_exists(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def directory_exists(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def list_dir(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def create_dir(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def delete_file(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def delete_dir(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_file_size(self, path: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def move_file(self, src: str, dst: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def copy_file(self, src: str, dst: str) -> Dict[str, Any]: ...


class BaseSystemHandler(ABC):
    """System-level operations (new for security scoping)."""

    @abstractmethod
    async def get_system_info(self) -> Dict[str, Any]: ...
    
    @abstractmethod
    async def get_env(self, key: str) -> Dict[str, Any]: ...
