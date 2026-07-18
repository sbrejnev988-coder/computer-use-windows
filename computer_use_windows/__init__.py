"""Computer Use Windows — Windows desktop control via MCP.

Version: 2.1.1 (Blocker Fixes)
  BL#1: PILImage import added (NameError fix)
  BL#2: FastMCP(instructions=...) not description=
  BL#3: @mcp.tool(annotations={"readOnlyHint": True, ...})
  PS: mouse_down/up: None,None → don't move cursor
  PS: keyboard VkKeyScanW resolver for letter/numeral keys
  PS: activate_window GetWindowThreadProcessId tuple fix
  PS: surrogate pairs for emoji (>U+FFFF)
  PS: frame_id bounds check (0 <= x < image_width)
  PS: single process-wide _PROCESS_INPUT_LOCK (shared remote+local)
  PS: remote PathPolicy enforcement for all file operations
"""

__version__ = "2.1.1"
__all__ = ["__version__"]
