# Computer Use Windows

> **Version 2.1.11** — Production-ready Windows desktop control MCP server.  
> **67 MCP tools** — screenshots, mouse/keyboard, window management, UI Automation, files, registry, services, shell.  
> **Native Win32 backend** — SendInput (Unicode + EXTENDEDKEY), SetForegroundWindow+AttachThreadInput, uiautomation ControlPatterns, win32service.  
> **Zero Node.js** — pure Python, runs on Windows 10/11 with Python 3.11+.

---

## Quick Start

```powershell
# Install from GitHub
pip install "git+https://github.com/sbrejnev988-coder/computer-use-windows.git"

# Or with installer
powershell -ExecutionPolicy Bypass -File install.ps1

# Optional extras
pip install "computer-use-windows[uia]"      # UI Automation
pip install "computer-use-windows[remote]"   # WebSocket server
pip install "computer-use-windows[all]"      # Everything

# Run local MCP server (stdio)
computer-use-windows mcp

# Run remote WebSocket server
$env:COMPUTER_USE_WINDOWS_TOKEN = "your-secret-token"
computer-use-windows remote --host 127.0.0.1 --port 8765

# Diagnostics
computer-use-windows doctor
```

## Security Profiles

Set `COMPUTER_USE_WINDOWS_PROFILE` to control tool access. Unknown profiles cause a fatal error — no silent fallback to full access.

| Profile | Scope | Default |
|---------|-------|---------|
| `observe` | Screenshots, windows, processes, system info (read-only) | |
| `desktop` | Mouse, keyboard, UIA, window management, clipboard | ✓ |
| `files` | File read/write/list within allowed directories | |
| `admin` | Shell, processes, registry, services, file delete | |
| `unsafe` | Full access — only when explicitly enabled | |

```powershell
$env:COMPUTER_USE_WINDOWS_PROFILE = "desktop"
```

**Important:** The `desktop` profile does **not** include file access. Use `files` or `admin` for file operations.

## Complete Tool Reference (67 tools)

### Observation (6)
| Tool | Description |
|------|-------------|
| `computer_screenshot` | Full virtual desktop screenshot with `frame_id` in `structured_content` |
| `computer_screenshot_region` | Capture region (validated: max 16384×16384, ≤64M pixels) |
| `computer_screenshot_window` | Capture window by HWND (screen crop — Graphics Capture planned) |
| `computer_get_screen_size` | Virtual desktop dimensions across all monitors |
| `computer_get_cursor_position` | Current cursor (x, y) in physical pixels |
| `computer_system_info` | OS, platform, DPI, monitor count, UIA availability |

### Mouse (8)
| Tool | Description |
|------|-------------|
| `computer_click` | Click at coordinates. button: `left`/`right`/`middle`. Uses `frame_id` for coordinate mapping |
| `computer_double_click` | Double-click. Checks first click before second |
| `computer_move` | Move cursor to coordinates |
| `computer_drag` | Smooth interpolated drag with `duration` (0.05–10s). Guaranteed mouse-up via `try/finally` |
| `computer_scroll` | Vertical + horizontal scroll in WHEEL_DELTA units (×120) |
| `computer_mouse_down` | Press button. `(None, None)` = current position |
| `computer_mouse_up` | Release button. Tracked in `_HELD_BUTTONS` |
| `computer_release_input_state` | Emergency: release all modifiers + mouse buttons + tracked keys |

### Keyboard (6)
| Tool | Description |
|------|-------------|
| `computer_type` | Type text via Unicode input — layout-independent, handles Cyrillic, emoji, all scripts. Atomic per-character SendInput batch |
| `computer_press_key` | Press physical key with guaranteed release on cancel |
| `computer_hotkey` | Key combination (Ctrl+C, Alt+F4). Full down-cycle in `try/finally`. Unknown keys fail-closed |
| `computer_key_down` | Hold physical key. Tracked in `_HELD_KEYS` |
| `computer_key_up` | Release physical key. Discarded from tracker only on SendInput success |

### Window Management (8)
| Tool | Description |
|------|-------------|
| `computer_activate_window` | Activate + bring to foreground (AttachThreadInput fallback). Returns `foreground_verified` |
| `computer_get_current_window` | Foreground window: HWND, title, class |
| `computer_get_app_windows` | Find windows by app name substring |
| `computer_list_windows` | All visible windows with titles/classes |
| `computer_resize_window` | Set window dimensions |
| `computer_minimize_window` | Minimize |
| `computer_maximize_window` | Maximize |
| `computer_restore_window` | Restore from minimized |
| `computer_close_window` | Send WM_CLOSE |

### UI Automation (13)
| Tool | Description |
|------|-------------|
| `computer_accessibility_tree` | Legacy HWND tree (EnumChildWindows) |
| `computer_find_element` | Find by title/class substring |
| `computer_get_ui_tree` | Full UIA tree with element IDs. Depth clamped 1–10, max 5000 nodes |
| `computer_find_ui_elements` | Search by `control_type`, `name`, `automation_id`, `class_name`. Max 50 results, 5000 nodes visited |
| `computer_focus_ui_element` | Set focus on UIA element |
| `computer_invoke_ui_element` | Click/invoke (InvokePattern → Click fallback) |
| `computer_set_ui_value` | Set value (ValuePattern → SendKeys fallback) |
| `computer_toggle_ui_element` | Toggle checkbox/switch (TogglePattern) |
| `computer_select_ui_element` | Select list item (SelectionItemPattern → Click fallback) |
| `computer_expand_ui_element` | Expand tree node (ExpandCollapsePattern) |
| `computer_scroll_ui_element_into_view` | Scroll into view (ScrollItemPattern → focus fallback) |
| `computer_wait_for_ui_element` | Poll until element appears (timeout in ms) |

All modifying UIA tools execute under the shared `_PROCESS_INPUT_LOCK`.

### Files (13)
| Tool | Description |
|------|-------------|
| `computer_file_read` | Read text file (1 MB limit) |
| `computer_file_write` | Write text file (atomic via `tempfile.mkstemp` + `os.replace`) |
| `computer_file_read_bytes` | Read binary with offset + length (max 10 MB, bounds enforced) |
| `computer_file_write_bytes` | Write binary (atomic) |
| `computer_file_exists` | Check file existence |
| `computer_directory_exists` | Check directory existence |
| `computer_list_dir` | List directory (max 1000 entries) |
| `computer_create_dir` | Create directory |
| `computer_delete_file` | Delete file (requires destructive profile) |
| `computer_delete_dir` | Delete directory recursively (requires destructive profile) |
| `computer_get_file_size` | File size in bytes |
| `computer_get_file_permissions` | File owner via security descriptor |
| `computer_move_file` | Move regular files only (directories rejected). Destructive protection on allowlist roots |
| `computer_copy_file` | Copy file |

All file paths are validated through `PathPolicy` — default roots: `~` and `%TEMP%`. Destructive operations (`delete_file`, `delete_dir`, `move_file`) additionally forbid operating on the allowlist roots themselves.

### Clipboard (2)
| Tool | Description |
|------|-------------|
| `computer_clipboard_get` | Read clipboard text |
| `computer_clipboard_set` | Set clipboard text |

### Shell & Launch (2)
| Tool | Description |
|------|-------------|
| `computer_run_command` | Shell command. Concurrent stdout/stderr streaming, 30s global timeout, 1 MB per stream. Returns `stdout_truncated`/`stderr_truncated` flags |
| `computer_launch` | Start application. No `shell=True` — args as list. Returns PID |

### Processes (2)
| Tool | Description |
|------|-------------|
| `computer_list_processes` | All processes (per-PID error handling) |
| `computer_kill_process` | Terminate by PID |

### Registry (2)
| Tool | Description |
|------|-------------|
| `computer_registry_read` | Read value. `REG_BINARY` returned as base64. Fail-closed on unknown root |
| `computer_registry_write` | Write value. All types: `REG_SZ`, `REG_DWORD`, `REG_QWORD`, `REG_BINARY` (base64), `REG_MULTI_SZ`, `REG_EXPAND_SZ`. Unknown type → ValueError |

### Services (4)
| Tool | Description |
|------|-------------|
| `computer_list_services` | Enumerate via `win32service` |
| `computer_service_status` | Query state (stopped/running/paused) |
| `computer_service_start` | Start service |
| `computer_service_stop` | Stop service |
| `computer_service_restart` | Restart via `win32serviceutil` |

## Coordinate System (Frame-aware)

Every screenshot returns `frame_id` in both `structured_content` and `TextContent`:

```json
{
  "frame_id": "frm_a1b2c3d4:e5f6a7b8c9d0",
  "capture_kind": "desktop",
  "left": -1920,
  "top": 0,
  "source_width": 5760,
  "source_height": 2160,
  "image_width": 1280,
  "image_height": 480
}
```

Mouse actions accept `frame_id` for correct coordinate transformation. Expired frames (desktop/window geometry changed) are rejected with a clear error. Coordinates outside frame bounds raise `ValueError`.

```
computer_click(x=640, y=240, frame_id="frm_a1b2c3d4:...")
  → physical click at (0, 1080) on center of left monitor
```

## Architecture

```
computer_use_windows/
├── __init__.py              # v2.1.11, exports __version__
├── cli.py                   # CLI: mcp | remote | doctor subcommands
├── remote.py                # WebSocket server with token auth + per-session isolation
├── handlers/
│   ├── __init__.py          # Platform detection — concrete stubs for non-Windows CI
│   ├── base.py              # Abstract interfaces: Automation, Accessibility, File, System
│   └── windows.py           # Win32 + UIA (1200+ lines)
│       ├── initialize_windows_runtime()  # DPI Per-Monitor V2 bootstrap
│       ├── SendInput         # Native input via ctypes (Unicode, EXTENDEDKEY, virtual desktop)
│       ├── UIA               # Single-threaded executor, ControlPatterns, element registry
│       ├── Services          # win32service (not sc.exe)
│       ├── Registry          # All types, fail-closed root parsing
│       └── Shell             # Concurrent streaming I/O, 30s timeout, 1MB cap
└── server/
    └── __init__.py           # FastMCP — 67 tools, capability profiles, PathPolicy, action lock
```

## Key Design Decisions

| Feature | Implementation |
|---------|---------------|
| Text input | Unicode-only via `KEYEVENTF_UNICODE` — layout-independent |
| Hotkeys | Physical-key resolver for letters/digits + special keys. Unknown keys fail-closed |
| Extended keys | `KEYEVENTF_EXTENDEDKEY` flag for arrows, Home/End, Ins/Del, PgUp/PgDn |
| SendInput | Every mouse/keyboard op checks `SendInput` return count. UIPI blocks reported |
| Cancel safety | `try/finally` on drag, hotkey, press_key, all clicks. `_HELD_KEYS`/`_HELD_BUTTONS` tracker |
| Emergency release | `computer_release_input_state` — tracked keys + modifiers + all mouse buttons |
| DPI | `SetProcessDpiAwarenessContext(-4)` = Per-Monitor V2. Bootstrapped in both MCP + remote |
| Frame coords | `Frame.to_screen()` with bounds check. Desktop hash invalidation. Frame registry |
| UIA | `ThreadPoolExecutor(max_workers=1)`. Depth ≤10, nodes ≤5000. `find_ui_elements` traverses children independently of parent match |
| Shell | Concurrent stdout/stderr reads, global 30s timeout, 1MB cap per stream, process killed on excess |
| Registry | Fail-closed root (`HKCU`/`HKLM`/`HKCR`/`HKU`/`HKCC`). All types. Binary via base64 |
| File writes | `tempfile.mkstemp` + `os.fsync` + `os.replace` — atomic, no race condition |
| PathPolicy | Allowlist roots (default: `~` and `%TEMP%`). Destructive ops forbidden on roots |
| Remote | `hmac.compare_digest` token auth. `max_size`/`max_queue`/`ping_interval` on WebSocket. Input ops serialized |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPUTER_USE_WINDOWS_TOKEN` | — | Auth token for remote WebSocket mode. Required for non-loopback bind |
| `COMPUTER_USE_WINDOWS_PROFILE` | `desktop` | Capability profile: `observe`, `desktop`, `files`, `admin`, `unsafe` |
| `COMPUTER_USE_WINDOWS_ALLOWED_ROOTS` | `~` + `%TEMP%` | Semicolon-separated paths for `PathPolicy` |

## Installation Options

```powershell
# Minimal (screenshots + mouse + keyboard + files)
pip install "git+https://github.com/sbrejnev988-coder/computer-use-windows.git"
# Windows deps (pywin32, psutil) auto-installed via platform markers

# With UI Automation
pip install "computer-use-windows[uia]"

# With remote WebSocket server
pip install "computer-use-windows[remote]"

# Everything
pip install "computer-use-windows[all]"

# Dev install
git clone https://github.com/sbrejnev988-coder/computer-use-windows.git
cd computer-use-windows
pip install -e ".[all]"
```

## Known Limitations

- **UIPI** prevents SendInput to elevated (admin) processes
- **Lock screen** and **secure desktop** are inaccessible
- `screenshot_window` uses screen crop (ImageGrab bbox) — Graphics Capture planned
- **Remote** uses plain WebSocket (`ws://`) — suitable for loopback, VPN, or reverse proxy with TLS termination
- **Remote** does not implement session resume (parameter accepted but ignored)
- **UIA/frame registries** have no automatic TTL cleanup (planned)
- Service management requires appropriate privileges

## Dependencies

```
fastmcp>=2.13.1,<3    # MCP server framework
Pillow>=10.0           # Screenshot capture + encoding
anyio>=4.0             # Async runtime abstraction
pywin32>=306           # Windows: Win32 API bindings (platform-conditional)
psutil>=5.9            # Windows: process management (platform-conditional)
uiautomation>=2.0      # Optional: UI Automation support
websockets>=12.0       # Optional: remote WebSocket server
mcp>=1.0               # MCP types (TextContent)
```

## Changelog

### v2.1.11 — Audit Round 13
- `_run_interactive_action()` unified wrapper: desktop lock check + input lock
- UIA `_build_tree` enforces `MAX_UIA_NODES=5000` via shared state
- Shell: drain excess output past 1MB limit (no pipe backpressure)
- Returns `stdout_truncated`/`stderr_truncated` flags

### v2.1.10 — Audit Round 12
- P0: `computer_click` NameError fix (removed stale helper call)
- Click executes under `_PROCESS_INPUT_LOCK`
- Remote: `_optional_xy` helper (fail-closed on partial coords)
- Remote: `release_input_state` capability mapping fixed

### v2.1.9 — Audit Round 11
- P0: `MAX_CAPTURE_DIM`/`MAX_CAPTURE_PIXELS` declared in handler
- Screenshot region validation moved to handler (protects MCP + remote)
- Shell: concurrent stdout/stderr reads + global 30s timeout
- UIA depth clamped in handler (max 10) for both transports

### v2.1.8 — Audit Round 10
- `KEYEVENTF_EXTENDEDKEY` for navigation keys (arrows, Home/End, Ins/Del)
- Atomic Unicode type_text per character (single SendInput batch)
- `press_key`/`hotkey` tracked in `_HELD_KEYS` for recovery
- Remote: `_required_xy` validation + `move_file` destructive flag

### v2.1.7 — Audit Round 9
- P0: `_HELD_BUTTONS` NameError regression fix
- `mouse_up` discards from tracker only after SendInput success
- `FastMCP(version=__version__)` — single source of truth

### v2.1.6 — Audit Round 8
- `press_key` → physical keys only (removed broken Unicode fallback)
- `drag` → fail-closed on unknown button
- `move_file` → regular files only + destructive flag
- `file_read_bytes` → bounds enforcement (offset/length)
- `_HELD_KEYS` → set, updated only after SendInput confirmation

### v2.1.5 — Audit Round 7
- Remote `delete_file`/`delete_dir` → `destructive=True`
- Remote UIA tools in `input_ops` (shared process-wide lock)
- `hotkey` → `release_ok` included in success result
- `press_key` → `try/finally` for key-up on cancel
- Mouse buttons → fail-closed (unknown button returns error, not wrong click)
- Non-Windows handlers → concrete `_UnsupportedHandler` stubs

### v2.1.4 — Audit Round 6
- P0 blocker: `TextContent` import fixed (`mcp.types`, not `fastmcp.utilities.types`)
- `type_text` → Unicode-only (layout-independent, no VkKeyScanW for text)
- `key_down`/`key_up` → fail-closed on non-physical keys
- `hotkey` → full down-cycle in `try/finally`
- UIA destructive tools → shared `_PROCESS_INPUT_LOCK`
- Registry → fail-closed on unknown type
- `PathPolicy.resolve(value, destructive=True)` + root protection

### v2.1.3 — Audit Round 5
- Physical-key resolver for letters/digits (Ctrl+C, Ctrl+V, Alt+F4)
- `hotkey` → fail-closed on unknown keys
- SendInput checked in drag/hotkey/clicks + try/finally
- All file ops → `asyncio.to_thread`
- `max_size` passed to `websockets.serve`
- UIA single-threaded executor
- `frame_id` in `structured_content` + `TextContent`
- Registry: all types, fail-closed root, binary via base64
- `tempfile.mkstemp` for atomic file writes

### v2.0.0 — Initial CISA Audit Release
- Native SendInput backend, UI Automation via `uiautomation`
- Frame coordinate system, `activate_window`, DPI Per-Monitor V2
- Capability profiles, `win32service`, secure remote transport

---

**License:** MIT  
**Repository:** https://github.com/sbrejnev988-coder/computer-use-windows
