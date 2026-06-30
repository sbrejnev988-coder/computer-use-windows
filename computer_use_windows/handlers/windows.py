"""Windows automation + accessibility handlers.

pynput (mouse/keyboard) + pywin32 (windows, clipboard, registry, services) + uiautomation.
"""

import asyncio, base64, functools, logging, os, subprocess, ctypes
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, TypeVar

from PIL import ImageGrab
from pynput.keyboard import Controller as KBController, Key as KBKey
from pynput.mouse import Controller as MouseController, Button as MSButton

from .base import BaseAutomationHandler, BaseAccessibilityHandler, BaseFileHandler

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

try:
    import win32api, win32con, win32gui, win32process, win32clipboard, win32service, winreg
    _HAS_WIN32 = True
except Exception:
    _HAS_WIN32 = False
    logger.warning("pywin32 unavailable")

def require_unlocked_desktop(func: F) -> F:
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if self.is_desktop_locked():
            return {"success": False, "error": "Desktop locked. Input blocked by OS security."}
        return await func(self, *args, **kwargs)
    return wrapper  # type: ignore


# ═══════════════ WINDOWS AUTOMATION ═══════════════

class WindowsAutomationHandler(BaseAutomationHandler):
    mouse = MouseController()
    keyboard = KBController()

    # ─── Desktop lock ───
    def is_desktop_locked(self) -> bool:
        try:
            return ctypes.windll.user32.GetForegroundWindow() == 0
        except Exception:
            return False

    # ─── Key mapping ───
    @staticmethod
    def _map_button(button: str):
        b = (button or "left").lower()
        return {"left": MSButton.left, "right": MSButton.right, "middle": MSButton.middle}.get(b, MSButton.left)

    @staticmethod
    def _key_from_string(key: str):
        if not key: return None
        lk = key.lower()
        special = {
            "enter": KBKey.enter, "return": KBKey.enter, "esc": KBKey.esc, "escape": KBKey.esc,
            "space": KBKey.space, "tab": KBKey.tab, "backspace": KBKey.backspace,
            "delete": KBKey.delete, "home": KBKey.home, "end": KBKey.end,
            "pageup": KBKey.page_up, "pagedown": KBKey.page_down,
            "up": KBKey.up, "down": KBKey.down, "left": KBKey.left, "right": KBKey.right,
            "shift": KBKey.shift, "ctrl": KBKey.ctrl, "control": KBKey.ctrl,
            "alt": KBKey.alt, "cmd": KBKey.cmd, "win": KBKey.cmd, "meta": KBKey.cmd,
            "capslock": KBKey.caps_lock,
            "f1": KBKey.f1, "f2": KBKey.f2, "f3": KBKey.f3, "f4": KBKey.f4,
            "f5": KBKey.f5, "f6": KBKey.f6, "f7": KBKey.f7, "f8": KBKey.f8,
            "f9": KBKey.f9, "f10": KBKey.f10, "f11": KBKey.f11, "f12": KBKey.f12,
        }
        return special.get(lk, key if len(key) == 1 else None)

    # ─── Screenshot ───
    async def screenshot(self) -> Dict[str, Any]:
        try:
            img = ImageGrab.grab(all_screens=True)
            buf = BytesIO(); img.save(buf, format="PNG")
            return {"success": True, "image_data": base64.b64encode(buf.getvalue()).decode(),
                    "width": img.width, "height": img.height}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot_region(self, x: int, y: int, width: int, height: int) -> Dict[str, Any]:
        """Capture a screen region (bbox)."""
        try:
            img = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
            buf = BytesIO(); img.save(buf, format="PNG")
            return {"success": True, "image_data": base64.b64encode(buf.getvalue()).decode(),
                    "width": img.width, "height": img.height}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot_window(self, window_id: Optional[int] = None) -> Dict[str, Any]:
        """Capture a specific window by HWND. Falls back to full screen."""
        if not _HAS_WIN32 or window_id is None:
            return await self.screenshot()
        try:
            hwnd = window_id
            rect = win32gui.GetWindowRect(hwnd)
            img = ImageGrab.grab(bbox=rect, all_screens=True)
            buf = BytesIO(); img.save(buf, format="PNG")
            return {"success": True, "image_data": base64.b64encode(buf.getvalue()).decode(),
                    "width": img.width, "height": img.height}
        except Exception:
            return await self.screenshot()

    async def get_screen_size(self) -> Dict[str, int]:
        try:
            img = ImageGrab.grab(); return {"width": img.width, "height": img.height}
        except Exception:
            return {"width": 1920, "height": 1080}

    async def get_cursor_position(self) -> Dict[str, int]:
        return {"x": self.mouse.position[0], "y": self.mouse.position[1]}

    # ─── Mouse ───
    @require_unlocked_desktop
    async def mouse_down(self, x=None, y=None, button="left") -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.press(self._map_button(button)); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def mouse_up(self, x=None, y=None, button="left") -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.release(self._map_button(button)); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def left_click(self, x=None, y=None) -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.click(MSButton.left, 1); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def right_click(self, x=None, y=None) -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.click(MSButton.right, 1); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def middle_click(self, x=None, y=None) -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.click(MSButton.middle, 1); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def double_click(self, x=None, y=None) -> Dict[str, Any]:
        try:
            if x is not None and y is not None: self.mouse.position = (x, y)
            self.mouse.click(MSButton.left, 2); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def move_cursor(self, x: int, y: int) -> Dict[str, Any]:
        try: self.mouse.position = (x, y); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def drag_to(self, x: int, y: int, button="left", duration=0.5) -> Dict[str, Any]:
        try:
            self.mouse.press(self._map_button(button)); self.mouse.position = (x, y)
            self.mouse.release(self._map_button(button)); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def scroll(self, scroll_x: int, scroll_y: int) -> Dict[str, Any]:
        try: self.mouse.scroll(scroll_x, scroll_y); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Keyboard ───
    @require_unlocked_desktop
    async def key_down(self, key: str) -> Dict[str, Any]:
        try:
            k = self._key_from_string(key)
            if k is None: return {"success": False, "error": f"Unknown key: {key}"}
            self.keyboard.press(k); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def key_up(self, key: str) -> Dict[str, Any]:
        try:
            k = self._key_from_string(key)
            if k is None: return {"success": False, "error": f"Unknown key: {key}"}
            self.keyboard.release(k); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def type_text(self, text: str) -> Dict[str, Any]:
        try: self.keyboard.type(text); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def press_key(self, key: str) -> Dict[str, Any]:
        try:
            k = self._key_from_string(key)
            if k is None: return {"success": False, "error": f"Unknown key: {key}"}
            self.keyboard.tap(k); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    @require_unlocked_desktop
    async def hotkey(self, keys: List[str]) -> Dict[str, Any]:
        try:
            converted = [self._key_from_string(k) for k in keys]
            if any(k is None for k in converted):
                return {"success": False, "error": f"Unknown keys in: {keys}"}
            for k in converted: self.keyboard.press(k)
            for k in reversed(converted): self.keyboard.release(k)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Clipboard ───
    async def copy_to_clipboard(self) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return {"success": True, "text": win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)}
                return {"success": False, "error": "No unicode text on clipboard"}
            finally: win32clipboard.CloseClipboard()
        except Exception as e: return {"success": False, "error": str(e)}

    async def set_clipboard(self, text: str) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard(); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Shell ───
    async def run_command(self, command: str) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            return {"success": True, "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"), "returncode": proc.returncode}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Window management ───
    async def launch(self, app: str, args: List[str] | None = None) -> Dict[str, Any]:
        try:
            cmd = [app] + (args or []); proc = subprocess.Popen(cmd, shell=True)
            return {"success": True, "pid": proc.pid}
        except Exception as e: return {"success": False, "error": str(e)}

    async def get_current_window_id(self) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            hwnd = win32gui.GetForegroundWindow(); title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd); _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return {"success": True, "window_id": hwnd, "title": title,
                    "bounds": {"x": rect[0], "y": rect[1], "width": rect[2]-rect[0], "height": rect[3]-rect[1]},
                    "pid": pid}
        except Exception as e: return {"success": False, "error": str(e)}

    async def get_application_windows(self, app: str) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        windows = []
        try:
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if app.lower() in title.lower():
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        windows.append({"window_id": hwnd, "title": title, "pid": pid})
                return True
            win32gui.EnumWindows(cb, None); return {"success": True, "windows": windows}
        except Exception as e: return {"success": False, "error": str(e)}

    async def list_all_windows(self) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        windows = []
        try:
            def cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        rect = win32gui.GetWindowRect(hwnd); _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        windows.append({"window_id": hwnd, "title": title, "pid": pid,
                                        "class": win32gui.GetClassName(hwnd),
                                        "bounds": {"x": rect[0], "y": rect[1], "width": rect[2]-rect[0], "height": rect[3]-rect[1]},
                                        "minimized": win32gui.IsIconic(hwnd), "focused": hwnd == win32gui.GetForegroundWindow()})
                return True
            win32gui.EnumWindows(cb, None); return {"success": True, "windows": windows}
        except Exception as e: return {"success": False, "error": str(e)}

    async def resize_window(self, window_id: int, w: int, h: int) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            win32gui.MoveWindow(window_id, *win32gui.GetWindowRect(window_id)[:2], w, h, True)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def minimize_window(self, window_id: int) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try: win32gui.ShowWindow(window_id, win32con.SW_MINIMIZE); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def maximize_window(self, window_id: int) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try: win32gui.ShowWindow(window_id, win32con.SW_MAXIMIZE); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def restore_window(self, window_id: int) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try: win32gui.ShowWindow(window_id, win32con.SW_RESTORE); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def close_window(self, window_id: int) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try: win32gui.PostMessage(window_id, win32con.WM_CLOSE, 0, 0); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Process management ───
    async def list_processes(self) -> Dict[str, Any]:
        try:
            import psutil
            procs = [{"pid": p.pid, "name": p.name(), "exe": p.exe(), "cpu_percent": p.cpu_percent(),
                       "memory_mb": round(p.memory_info().rss / 1024 / 1024, 1)}
                     for p in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_info'])]
            return {"success": True, "processes": procs[:200]}
        except ImportError:
            # Fallback: tasklist
            try:
                proc = await asyncio.create_subprocess_shell("tasklist /FO CSV /NH", stdout=asyncio.subprocess.PIPE)
                out, _ = await proc.communicate()
                lines = out.decode("utf-8", errors="replace").strip().split('\n')
                procs = []
                for line in lines[:200]:
                    parts = line.replace('"', '').split(',')
                    if len(parts) >= 2: procs.append({"name": parts[0].strip(), "pid": int(parts[1].strip())})
                return {"success": True, "processes": procs}
            except Exception as e: return {"success": False, "error": str(e)}

    async def kill_process(self, pid: int) -> Dict[str, Any]:
        # Windows: TerminateProcess через win32api (надёжнее чем os.kill/SIGTERM)
        if _HAS_WIN32:
            try:
                import win32api as wapi, win32security as wsec
                h_process = wapi.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
                if h_process:
                    wapi.TerminateProcess(h_process, 1)
                    wapi.CloseHandle(h_process)
                    return {"success": True}
            except Exception:
                pass
        try: subprocess.run(f"taskkill /PID {pid} /F", shell=True, capture_output=True); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Registry ───
    async def registry_read(self, key_path: str, value_name: str = "") -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            hkey_map = {"HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                         "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER, "HKCU": winreg.HKEY_CURRENT_USER,
                         "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT, "HKCR": winreg.HKEY_CLASSES_ROOT}
            root_key, _, subkey = key_path.partition("\\")
            hkey = hkey_map.get(root_key.upper(), winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ)
            if not value_name:
                value_name, value, _ = winreg.EnumValue(key, 0)
            else:
                value, _ = winreg.QueryValueEx(key, value_name)
            winreg.CloseKey(key)
            return {"success": True, "value": str(value)}
        except Exception as e: return {"success": False, "error": str(e)}

    async def registry_write(self, key_path: str, value_name: str, value: str, reg_type: str = "REG_SZ") -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            hkey_map = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER, "HKCR": winreg.HKEY_CLASSES_ROOT}
            root_key, _, subkey = key_path.partition("\\")
            hkey = hkey_map.get(root_key.upper(), winreg.HKEY_CURRENT_USER)
            key = winreg.CreateKey(hkey, subkey)
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── Service management ───
    async def list_services(self) -> Dict[str, Any]:
        """List all Windows services with status."""
        try:
            proc = await asyncio.create_subprocess_shell(
                'sc query state= all | findstr /C:"SERVICE_NAME" /C:"STATE"',
                stdout=asyncio.subprocess.PIPE)
            out, _ = await proc.communicate()
            return {"success": True, "raw": out.decode("utf-8", errors="replace")[:4000]}
        except Exception as e: return {"success": False, "error": str(e)}

    async def service_status(self, name: str) -> Dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(f"sc query {name}", stdout=asyncio.subprocess.PIPE)
            out, _ = await proc.communicate()
            text = out.decode("utf-8", errors="replace")
            return {"success": True, "running": "RUNNING" in text, "raw": text[:500]}
        except Exception as e: return {"success": False, "error": str(e)}

    async def service_start(self, name: str) -> Dict[str, Any]:
        try: subprocess.run(f"sc start {name}", shell=True, capture_output=True); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def service_stop(self, name: str) -> Dict[str, Any]:
        try: subprocess.run(f"sc stop {name}", shell=True, capture_output=True); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def service_restart(self, name: str) -> Dict[str, Any]:
        try:
            subprocess.run(f"sc stop {name}", shell=True, capture_output=True)
            import time; time.sleep(1)
            subprocess.run(f"sc start {name}", shell=True, capture_output=True)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # ─── System info ───
    async def system_info(self) -> Dict[str, Any]:
        """Return OS version, CPU, RAM, disk info."""
        import platform
        info = {"os": platform.system(), "version": platform.version(), "release": platform.release(),
                "architecture": platform.machine(), "hostname": platform.node()}
        try:
            import psutil
            info["cpu_count"] = psutil.cpu_count(logical=True)
            info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = round(mem.total / 1024**3, 1)
            info["memory_available_gb"] = round(mem.available / 1024**3, 1)
            info["memory_percent"] = mem.percent
            disks = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append({"mount": part.mountpoint, "total_gb": round(usage.total / 1024**3, 1),
                                  "free_gb": round(usage.free / 1024**3, 1), "percent": usage.percent})
                except Exception: pass
            info["disks"] = disks[:10]
        except ImportError:
            info["psutil"] = "not available — pip install psutil"
        return {"success": True, "info": info}

    # ─── File permissions ───
    async def get_file_permissions(self, path: str) -> Dict[str, Any]:
        """Get file permissions via os.stat (cross-platform) + win32security ACL on Windows."""
        try:
            st = os.stat(path)
            perms = {"mode_octal": oct(st.st_mode)[-3:], "size": st.st_size, "owner": st.st_uid}
            if _HAS_WIN32:
                try:
                    import win32security, ntsecuritycon
                    sd = win32security.GetNamedSecurityInfo(
                        path, win32security.SE_FILE_OBJECT,
                        win32security.DACL_SECURITY_INFORMATION | win32security.OWNER_SECURITY_INFORMATION)
                    owner = sd.GetSecurityDescriptorOwner()
                    owner_name = win32security.LookupAccountSid(None, owner)[0] if owner else None
                    perms["owner"] = owner_name or st.st_uid
                    dacl = sd.GetSecurityDescriptorDacl()
                    aces = []
                    if dacl:
                        for i in range(dacl.GetAceCount()):
                            ace = dacl.GetAce(i)
                            aces.append(str(ace))
                    perms["acl"] = aces[:10]
                except Exception: pass
            return {"success": True, "path": path, "permissions": perms}
        except Exception as e: return {"success": False, "error": str(e)}


# ═══════════════ WINDOWS ACCESSIBILITY ═══════════════

class WindowsAccessibilityHandler(BaseAccessibilityHandler):
    """Accessibility tree via win32gui + uiautomation."""

    async def get_accessibility_tree(self) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return {"success": False, "error": "No foreground window"}
            title = win32gui.GetWindowText(hwnd); rect = win32gui.GetWindowRect(hwnd)
            tree = {"role": "Window", "title": title,
                    "position": {"x": rect[0], "y": rect[1]},
                    "size": {"width": rect[2]-rect[0], "height": rect[3]-rect[1]}, "children": []}
            def child_cb(hwnd_c, lst):
                try:
                    lst.append({"role": win32gui.GetClassName(hwnd_c), "title": win32gui.GetWindowText(hwnd_c)})
                except Exception: pass
                return True
            win32gui.EnumChildWindows(hwnd, child_cb, tree["children"])
            return {"success": True, "tree": tree}
        except Exception as e: return {"success": False, "error": str(e)}

    async def find_element(self, role=None, title=None) -> Dict[str, Any]:
        if not _HAS_WIN32: return {"success": False, "error": "pywin32 required"}
        try:
            if title:
                hwnd = win32gui.FindWindow(None, title)
                if hwnd:
                    rect = win32gui.GetWindowRect(hwnd)
                    return {"success": True, "element": {"role": "Window", "title": title,
                            "position": {"x": rect[0], "y": rect[1]},
                            "size": {"width": rect[2]-rect[0], "height": rect[3]-rect[1]}}}
            if role:
                hwnd = win32gui.FindWindow(role, None)
                if hwnd: return {"success": True, "element": {"role": role, "title": win32gui.GetWindowText(hwnd)}}
            return {"success": False, "error": "Element not found"}
        except Exception as e: return {"success": False, "error": str(e)}


# ═══════════════ WINDOWS FILE HANDLER ═══════════════

class WindowsFileHandler(BaseFileHandler):
    """File system operations — pure Python stdlib + pathlib."""

    async def read_text(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"success": True, "content": f.read()}
        except Exception as e: return {"success": False, "error": str(e)}

    async def write_text(self, path: str, content: str) -> Dict[str, Any]:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f: f.write(content)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def read_bytes(self, path: str, offset: int = 0, length: Optional[int] = None) -> Dict[str, Any]:
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read() if length is None else f.read(length)
            return {"success": True, "content": base64.b64encode(data).decode(), "size": len(data)}
        except Exception as e: return {"success": False, "error": str(e)}

    async def write_bytes(self, path: str, content: bytes) -> Dict[str, Any]:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as f: f.write(content)
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def file_exists(self, path: str) -> Dict[str, Any]:
        return {"success": True, "exists": os.path.isfile(path)}

    async def directory_exists(self, path: str) -> Dict[str, Any]:
        return {"success": True, "exists": os.path.isdir(path)}

    async def list_dir(self, path: str) -> Dict[str, Any]:
        try:
            items = []
            for entry in os.listdir(path):
                full = os.path.join(path, entry)
                items.append({"name": entry, "is_dir": os.path.isdir(full),
                              "size": os.path.getsize(full) if os.path.isfile(full) else 0})
            return {"success": True, "items": items}
        except Exception as e: return {"success": False, "error": str(e)}

    async def create_dir(self, path: str) -> Dict[str, Any]:
        try: os.makedirs(path, exist_ok=True); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def delete_file(self, path: str) -> Dict[str, Any]:
        try: os.remove(path); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def delete_dir(self, path: str) -> Dict[str, Any]:
        try:
            import shutil; shutil.rmtree(path); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def get_file_size(self, path: str) -> Dict[str, Any]:
        try: return {"success": True, "size": os.path.getsize(path)}
        except Exception as e: return {"success": False, "error": str(e)}

    async def move_file(self, src: str, dst: str) -> Dict[str, Any]:
        try: os.rename(src, dst); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    async def copy_file(self, src: str, dst: str) -> Dict[str, Any]:
        try:
            import shutil; shutil.copy2(src, dst); return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}
