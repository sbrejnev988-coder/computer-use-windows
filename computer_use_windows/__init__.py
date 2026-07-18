"""Computer Use Windows — Windows desktop control via MCP.

Version: 2.0.0 (CISA Red Team Audit Fix)
  - P0: remote imports, async entry point, frame_id coords, activate_window
  - P0: DPI Per-Monitor V2, screenshot error propagation, doctor diagnostics
  - P1: native SendInput, UI Automation, action lock, capability profiles
  - P2: win32service, scoped operations, secure remote transport
"""

__version__ = "2.0.0"
__all__ = ["__version__"]
