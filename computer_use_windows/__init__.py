"""Computer Use Windows — Windows desktop control via MCP.

Version: 2.1.0 (CISA Audit Round 2)
  P0#1: screenshot → ToolResult (not Image with _meta)
  P0#2: computer_scroll → move + scroll(scroll_x, scroll_y)
  P0#3: computer_drag → move to start first
  P0#4: Frame validation — desktop_hash + registry, not last_frame
  P0#5: CLI remote — pass args directly, no re-parse
  P0#6: capability policy → fail-closed + require_capability decorator
  P0#7: PathPolicy — allowed roots, resolve, symlink check
  P0#8: remote timeout — wraps actual operation, not lambda thread
"""

__version__ = "2.1.0"
__all__ = ["__version__"]
