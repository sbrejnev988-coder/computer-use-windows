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
    # Concrete stubs for non-Windows (CI, smoke-test, inspection)
    # Return {"success": False, "error": "Windows required"} for all methods
    from typing import Any, Dict, List, Optional

    class _UnsupportedHandler:
        """Stub handler — all methods return Windows-required error."""
        async def _unsupported(self, *args, **kwargs) -> Dict[str, Any]:
            return {"success": False, "error": "Windows is required for this operation"}
        def __getattr__(self, name):
            # Any method call returns the error dict via coroutine
            async def _stub(*args, **kwargs):
                return {"success": False, "error": "Windows is required for this operation"}
            return _stub

    WindowsAutomationHandler = _UnsupportedHandler
    WindowsAccessibilityHandler = _UnsupportedHandler
    WindowsFileHandler = _UnsupportedHandler
    WindowsSystemHandler = _UnsupportedHandler

__all__ = [
    "WindowsAutomationHandler",
    "WindowsAccessibilityHandler",
    "WindowsFileHandler",
    "WindowsSystemHandler",
    "_HAS_WIN32",
]
