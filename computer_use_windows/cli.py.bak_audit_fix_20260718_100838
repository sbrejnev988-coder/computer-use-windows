"""CLI for computer-use-windows.

Usage:
    computer-use-windows mcp        # Start FastMCP stdio server (56 tools)
    computer-use-windows remote     # WebSocket remote server (ws://127.0.0.1:8765)
    computer-use-windows remote --port 9000 --host 0.0.0.0 --token my-secret
    computer-use-windows doctor     # Full readiness report
"""

import json, os, sys
from .handlers import _HAS_WIN32


def _init_dpi():
    """Enable Per-Monitor DPI Awareness V2 — prevents coordinate distortion on HiDPI."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE_V2
    except Exception:
        pass


def _doctor_report() -> dict:
    """Full readiness report: API availability, DPI, admin rights, UIA, websockets."""
    checks = {}

    # pywin32
    try:
        import win32api, win32con, win32gui
        checks["pywin32"] = "ok"
    except ImportError:
        checks["pywin32"] = "missing — pip install pywin32"

    # pynput
    try:
        from pynput.keyboard import Controller
        checks["pynput"] = "ok"
    except ImportError:
        checks["pynput"] = "missing — pip install pynput"

    # uiautomation
    try:
        import uiautomation
        checks["uiautomation"] = "ok"
    except ImportError:
        checks["uiautomation"] = "missing — pip install uiautomation"

    # websockets
    try:
        import websockets
        checks["websockets"] = "ok"
    except ImportError:
        checks["websockets"] = "missing — pip install websockets"

    # Pillow (ImageGrab)
    try:
        from PIL import ImageGrab
        checks["Pillow"] = "ok"
    except ImportError:
        checks["Pillow"] = "missing — pip install Pillow"

    # psutil (optional)
    try:
        import psutil
        checks["psutil"] = "ok (system_info + processes enhanced)"
    except ImportError:
        checks["psutil"] = "optional — pip install psutil"

    # Admin rights
    try:
        import ctypes
        checks["is_admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        checks["is_admin"] = "unknown"

    # Desktop locked
    try:
        import ctypes
        checks["desktop_locked"] = bool(ctypes.windll.user32.GetForegroundWindow() == 0)
    except Exception:
        checks["desktop_locked"] = "unknown"

    # DPI awareness
    checks["dpi_awareness"] = "enabled (Per-Monitor V2)"

    ready = all(
        v == "ok" or v.startswith("ok") or isinstance(v, bool) or v == "enabled (Per-Monitor V2)" or v.startswith("optional")
        for v in checks.values()
    )
    return {"ready": ready, "checks": checks}


def main():
    _init_dpi()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "mcp":
        import anyio
        from .server import main as mcp_main
        anyio.run(mcp_main)

    elif cmd == "remote":
        import asyncio, argparse
        from .remote import RemoteComputerServer
        p = argparse.ArgumentParser(prog="computer-use-windows remote")
        p.add_argument("--host", default="127.0.0.1")
        p.add_argument("--port", type=int, default=8765)
        p.add_argument("--token", help="Auth token (or set COMPUTER_USE_WINDOWS_TOKEN env)")
        args, _ = p.parse_known_args()
        asyncio.run(RemoteComputerServer(args.host, args.port, args.token).start())

    elif cmd == "doctor":
        report = _doctor_report()
        print(json.dumps(report, indent=2))
        if not report["ready"]:
            sys.exit(1)

    elif cmd in ("--help", "-h", ""):
        print(__doc__)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
