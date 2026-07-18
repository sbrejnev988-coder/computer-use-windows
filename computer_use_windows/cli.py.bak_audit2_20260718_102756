"""Command-line interface for Computer Use Windows.

Two modes:
  computer-use-windows mcp          → local MCP server (stdio)
  computer-use-windows-mcp           → same (console entry point)
  computer-use-windows remote       → WebSocket remote server

CISA Audit v2.0 fix: entry points use sync main() with anyio.run().
"""

import argparse, asyncio, logging, os, sys

from .handlers import _HAS_WIN32

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("computer-use-windows")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Computer Use Windows — MCP server for Windows desktop control"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # MCP stdio mode
    mcp_parser = sub.add_parser("mcp", help="Start local MCP server (stdio)")

    # Remote WebSocket mode
    remote_parser = sub.add_parser("remote", help="Start remote WebSocket server")
    remote_parser.add_argument("--host", default="127.0.0.1")
    remote_parser.add_argument("--port", type=int, default=8765)
    remote_parser.add_argument("--token", default=None)

    # Doctor — diagnostic check
    doctor_parser = sub.add_parser("doctor", help="Run capability diagnostics")

    args = parser.parse_args()

    if args.command == "mcp":
        if not _HAS_WIN32:
            logger.error("MCP server requires Windows. Use remote mode or run on Windows.")
            sys.exit(1)
        from .server import main as mcp_main
        mcp_main()

    elif args.command == "remote":
        from .remote import RemoteComputerServer, main as remote_main
        remote_main()

    elif args.command == "doctor":
        _run_doctor()


def _run_doctor() -> None:
    """Run capability diagnostics (P0 fix: real checks, not hardcoded)."""
    print("=== Computer Use Windows Doctor ===")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version}")

    checks = []

    # Win32 check
    checks.append(("Win32 platform", sys.platform == "win32"))

    # psutil
    try:
        import psutil
        checks.append(("psutil", True))
    except ImportError:
        checks.append(("psutil", False))

    # PIL/Pillow
    try:
        from PIL import ImageGrab
        checks.append(("PIL.ImageGrab", True))
    except ImportError:
        checks.append(("PIL.ImageGrab", False))

    # win32api
    try:
        import win32api
        checks.append(("pywin32", True))
    except ImportError:
        checks.append(("pywin32", False))

    # uiautomation
    try:
        import uiautomation
        checks.append(("uiautomation", True))
    except ImportError:
        checks.append(("uiautomation", False))

    # websockets
    try:
        import websockets
        checks.append(("websockets", True))
    except ImportError:
        checks.append(("websockets", False))

    # pynput
    try:
        from pynput.keyboard import Controller
        checks.append(("pynput", True))
    except ImportError:
        checks.append(("pynput", False))

    # DPI awareness (Windows only)
    if sys.platform == "win32":
        import ctypes
        try:
            user32 = ctypes.windll.user32
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            ok = user32.SetProcessDpiAwarenessContext(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            )
            checks.append(("DPI Per-Monitor V2", bool(ok)))
        except Exception as e:
            checks.append(("DPI Per-Monitor V2", False))

        # Desktop lock check
        try:
            hdesk = user32.OpenInputDesktop(0, False, 0x0001)
            if hdesk:
                user32.CloseDesktop(hdesk)
                checks.append(("Desktop accessible", True))
            else:
                checks.append(("Desktop accessible", False))
        except Exception:
            checks.append(("Desktop accessible", False))

        # SendInput test
        try:
            from ctypes import wintypes
            # Just verify the DLL loads
            user32.SendInput
            checks.append(("SendInput (native)", True))
        except Exception:
            checks.append(("SendInput (native)", False))

    # FastMCP
    try:
        from fastmcp import FastMCP
        checks.append(("FastMCP", True))
    except ImportError:
        checks.append(("FastMCP", False))

    # anyio
    try:
        import anyio
        checks.append(("anyio", True))
    except ImportError:
        checks.append(("anyio", False))

    # Print results
    all_ok = True
    for name, ok in checks:
        status = "✓" if ok else "✗"
        if not ok:
            all_ok = False
        print(f"  {status} {name}")

    print(f"\nOverall: {'PASS' if all_ok else 'FAIL — missing dependencies'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
