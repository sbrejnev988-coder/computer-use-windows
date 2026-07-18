# Computer Use Windows

> **Version 2.0.0** — CISA Red Team Audit: production-grade Windows desktop control MCP server.  
> **57 MCP tools** — screenshots, mouse/keyboard, window management, UI Automation, files, registry, services, shell.  
> **Native Win32 backend** — SendInput (Unicode), SetForegroundWindow+AttachThreadInput, uiautomation ControlPatterns, win32service.  
> **Zero Node.js dependency** — pure Python (optional: uiautomation, websockets, pywin32), runs on Windows with Python 3.11+.

---

## Quick Start

```powershell
# Install
powershell -ExecutionPolicy Bypass -File install.ps1

# With UI Automation
powershell -ExecutionPolicy Bypass -File install.ps1 -UIA

# Run local MCP server
computer-use-windows mcp

# Run remote WebSocket server
$env:COMPUTER_USE_WINDOWS_TOKEN = "your-secret-token"
computer-use-windows remote --host 0.0.0.0 --port 8765

# Diagnostics
computer-use-windows doctor
```

## Security Profiles

Set `COMPUTER_USE_WINDOWS_PROFILE` to control tool access:

| Profile | Access |
|---------|--------|
| `observe` | Screenshots, windows, processes, system info (read-only) |
| `desktop` | Mouse, keyboard, UIA, window management, clipboard **(default)** |
| `files` | File read/write/list within allowed directories |
| `admin` | Shell, processes, registry, services |
| `unsafe` | Full access — only when explicitly enabled |

```powershell
$env:COMPUTER_USE_WINDOWS_PROFILE = "desktop"  # default
```

## Complete Tool Reference

### Observation (8 tools)
| Tool | Description |
|------|-------------|
| `computer_screenshot` | Full virtual desktop screenshot with frame_id metadata |
| `computer_screenshot_region` | Capture region (x, y, width, height) |
| `computer_screenshot_window` | Capture window by HWND |
| `computer_get_screen_size` | Virtual desktop dimensions |
| `computer_get_cursor_position` | Current cursor (x, y) |
| `computer_system_info` | OS, platform, DPI, monitors, UIA availability |
| `computer_get_file_permissions` | File owner/security descriptor info |
| `computer_list_windows` | All visible windows with titles/classes |

### Mouse (10 tools)
| Tool | Description |
|------|-------------|
| `computer_click` | Left/right/middle click at coordinates (frame-aware) |
| `computer_double_click` | Double-click at coordinates |
| `computer_move` | Move cursor |
| `computer_drag` | Smooth drag with interpolated movement |
| `computer_scroll` | Vertical + horizontal scroll |
| `computer_mouse_down` | Press mouse button |
| `computer_mouse_up` | Release mouse button |

### Keyboard (5 tools)
| Tool | Description |
|------|-------------|
| `computer_type` | Type text (Unicode: Cyrillic, emoji, any script) |
| `computer_press_key` | Press single key (name or char) |
| `computer_hotkey` | Key combination (Ctrl+C, Alt+Tab, etc.) |
| `computer_key_down` | Hold key |
| `computer_key_up` | Release key |

### Window Management (8 tools)
| Tool | Description |
|------|-------------|
| `computer_activate_window` | Activate + bring to foreground (AttachThreadInput fallback) |
| `computer_get_current_window` | Foreground window info |
| `computer_get_app_windows` | Find windows by app name |
| `computer_resize_window` | Set window dimensions |
| `computer_minimize_window` | Minimize |
| `computer_maximize_window` | Maximize |
| `computer_restore_window` | Restore from minimized |
| `computer_close_window` | Send WM_CLOSE |

### UI Automation (13 tools)
| Tool | Description |
|------|-------------|
| `computer_accessibility_tree` | Legacy HWND tree (EnumChildWindows) |
| `computer_find_element` | Find by title/class |
| `computer_get_ui_tree` | **Full UIA tree** with element IDs, ControlTypes, names |
| `computer_find_ui_elements` | Search by control_type, name, automation_id, class_name |
| `computer_focus_ui_element` | Set focus on UIA element |
| `computer_invoke_ui_element` | Click/invoke (InvokePattern) |
| `computer_set_ui_value` | Set value (ValuePattern) |
| `computer_toggle_ui_element` | Toggle checkbox/switch (TogglePattern) |
| `computer_select_ui_element` | Select list item (SelectionItemPattern) |
| `computer_expand_ui_element` | Expand tree node (ExpandCollapsePattern) |
| `computer_scroll_ui_element_into_view` | Scroll element into view (ScrollItemPattern) |
| `computer_wait_for_ui_element` | Poll until element appears |

### Files (12 tools)
| Tool | Description |
|------|-------------|
| `computer_file_read` | Read text file |
| `computer_file_write` | Write text file |
| `computer_file_read_bytes` | Read binary (offset + length) |
| `computer_file_write_bytes` | Write binary (base64) |
| `computer_file_exists` | Check file |
| `computer_directory_exists` | Check directory |
| `computer_list_dir` | List directory contents |
| `computer_create_dir` | Create directory |
| `computer_delete_file` | Delete file (admin profile) |
| `computer_delete_dir` | Delete directory recursively (admin profile) |
| `computer_get_file_size` | File size |
| `computer_move_file` / `computer_copy_file` | Move/copy |

### System & Admin (14 tools)
| Tool | Description |
|------|-------------|
| `computer_run_command` | Shell command (30s timeout, 1MB output limit) |
| `computer_launch` | Start application (args list, no shell injection) |
| `computer_clipboard_get` / `computer_clipboard_set` | Clipboard read/write |
| `computer_list_processes` | All processes (per-PID error handling) |
| `computer_kill_process` | Terminate by PID |
| `computer_registry_read` / `computer_registry_write` | Registry operations (all types) |
| `computer_list_services` | Enumerate services |
| `computer_service_status` / `service_start` / `service_stop` / `service_restart` | Service control (win32service) |

## Architecture

```
computer_use_windows/
├── __init__.py          # Package metadata, v2.0.0
├── cli.py               # CLI: mcp, remote, doctor subcommands
├── remote.py            # WebSocket remote server with token auth
├── handlers/
│   ├── __init__.py      # Platform detection, handler exports
│   ├── base.py          # Abstract base classes (Automation, Accessibility, File, System)
│   └── windows.py       # Win32 implementation (1293 lines)
│       ├── SendInput    # Native input via ctypes (Unicode, virtual desktop)
│       ├── DPI          # Per-Monitor V2 via SetProcessDpiAwarenessContext
│       ├── UIA          # UI Automation via uiautomation library
│       ├── Services     # win32service (not sc.exe)
│       └── Registry     # All REG_ types supported
└── server/
    └── __init__.py      # FastMCP server with 57 tools, capability profiles, action lock
```

## Coordinate System (Frame-aware)

Every screenshot returns a `frame_id` with geometry metadata:

```json
{
  "frame_id": "frm_a1b2c3d4:e5f6a7b8c9d0",
  "left": -1920,
  "top": 0,
  "source_width": 5760,
  "source_height": 2160,
  "image_width": 1280,
  "image_height": 480
}
```

Mouse actions accept `frame_id` for correct coordinate transformation:

```
computer_click(x=640, y=240, frame_id="frm_a1b2c3d4:...")
  → physical click at (0, 1080) on center of left monitor
```

Expired frames (desktop/window geometry changed) are rejected.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPUTER_USE_WINDOWS_TOKEN` | — | Auth token for remote WebSocket mode |
| `COMPUTER_USE_WINDOWS_PROFILE` | `desktop` | Capability profile (observe/desktop/files/admin/unsafe) |

## Installation Options

```powershell
# Minimal (screenshots + mouse + keyboard)
pip install git+https://github.com/sbrejnev988-coder/computer-use-windows.git
pip install pywin32 psutil

# With UI Automation (Chromium, Electron, WPF, UWP)
pip install uiautomation

# With remote server
pip install websockets

# Dev install
git clone https://github.com/sbrejnev988-coder/computer-use-windows.git
cd computer-use-windows
pip install -e ".[win32,uia,remote]"
```

## Known Limitations

- UIPI prevents SendInput to elevated (admin) processes
- Lock screen and secure desktop are inaccessible
- Remote mode requires network access and securely configured token
- Service management requires appropriate privileges

## License

MIT — see [LICENSE](LICENSE)

## Changelog

### v2.0.0 — CISA Red Team Audit
- **P0**: Remote imports fixed, async entry point, frame_id coords, activate_window, DPI V2, error propagation, doctor
- **P1**: Native SendInput, UI Automation, action lock, drag interpolation, Unicode keyboard
- **P2**: Capability profiles, win32service, secure remote, shell timeout, clipboard fix, registry types

### v1.0.0 — Initial Release
- 13 MCP tools: screenshots, pynput mouse/keyboard, basic window management
- FastMCP server, Win32 API backend (pynput + pywin32)
