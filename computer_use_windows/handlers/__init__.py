"""computer-use-windows handlers.

Re-exports:
- BaseAutomationHandler, BaseAccessibilityHandler, BaseFileHandler (from .base)
- WindowsAutomationHandler, WindowsAccessibilityHandler, WindowsFileHandler (from .windows)
- require_unlocked_desktop decorator
- _HAS_WIN32 flag
"""

from .base import BaseAutomationHandler, BaseAccessibilityHandler, BaseFileHandler
from .windows import (
    WindowsAutomationHandler,
    WindowsAccessibilityHandler,
    WindowsFileHandler,
    require_unlocked_desktop,
    _HAS_WIN32,
)
