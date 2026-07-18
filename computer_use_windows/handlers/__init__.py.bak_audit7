"""Handler exports — platform detection and factory."""

import sys

_HAS_WIN32 = sys.platform == "win32"

if _HAS_WIN32:
    from .windows import (
        WindowsAutomationHandler,
        WindowsAccessibilityHandler,
        WindowsFileHandler,
        WindowsSystemHandler,
    )
else:
    # Stubs for non-Windows (testing, inspection)
    from .base import (
        BaseAutomationHandler as WindowsAutomationHandler,
        BaseAccessibilityHandler as WindowsAccessibilityHandler,
        BaseFileHandler as WindowsFileHandler,
        BaseSystemHandler as WindowsSystemHandler,
    )

__all__ = [
    "WindowsAutomationHandler",
    "WindowsAccessibilityHandler",
    "WindowsFileHandler",
    "WindowsSystemHandler",
    "_HAS_WIN32",
]
