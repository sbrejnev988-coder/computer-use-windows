<div align="center">
  <h1>computer-use-windows 🖥️</h1>
  <p><strong>Windows desktop control via MCP — native Win32 API backend</strong></p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/Platform-Windows%2010%2B-blue" alt="Windows 10+">
    <img src="https://img.shields.io/badge/Python-3.12%2B-green" alt="Python 3.12+">
  </p>
</div>

Адаптировано из [trycua/cua](https://github.com/trycua/cua) — Computer Use Agent. Это самостоятельный Python-пакет для локального Windows-управления через MCP (Model Context Protocol).

## Что это

`computer-use-windows` — Python MCP-сервер для Windows desktop control:

- **UI Automation** — чтение accessibility-дерева (`uiautomation`)
- **Скриншоты** — DXGI Desktop Duplication + GDI `BitBlt` fallback
- **Ввод** — `SendInput` API (клики, драг, скролл, клавиатура, Unicode-ввод)
- **Окна** — `EnumWindows`, `SetForegroundWindow` через `pywin32`

## Установка

```powershell
# Требования: Python 3.12+, Windows 10+

pip install computer-use-windows

# Проверить готовность
computer-use-windows doctor
```

### Из исходников

```powershell
git clone https://github.com/YOUR/cua-windows
cd cua-windows
pip install -e ".[dev,dxgi]"
computer-use-windows doctor
```

## Использование

### CLI

```powershell
computer-use-windows mcp          # Запуск MCP-сервера (stdio)
computer-use-windows doctor       # JSON отчёт о готовности
computer-use-windows screenshot   # Скриншот → screenshot.png
computer-use-windows windows       # Список видимых окон
computer-use-windows apps          # UIA accessibility дерево
```

### MCP (Claude Desktop)

Отредактируйте `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "computer-use-windows": {
      "command": "computer-use-windows",
      "args": ["mcp"]
    }
  }
}
```

### MCP (Hermes Agent)

```bash
hermes mcp add computer-use-windows --command computer-use-windows --args mcp
hermes mcp test computer-use-windows
```

## MCP-инструменты

| Инструмент | Описание |
|------------|----------|
| `doctor` | JSON readiness report |
| `screenshot` | Захват экрана (PNG/JPEG, макс. 1920px/2MB) |
| `list_windows` | Все видимые окна (title, HWND, PID, bounds) |
| `focused_window` | Окно в фокусе |
| `activate_window` | Активировать окно по HWND |
| `get_app_state` | Скриншот + UIA-дерево |
| `click` | Клик по координатам (x, y) |
| `drag` | Драг от start до end |
| `scroll` | Скролл в координатах |
| `press_key` | Нажатия клавиш (`ctrl+c`, `alt+tab`, `enter`) |
| `type_text` | Unicode-ввод текста |
| `perform_action` | UIA-действие (Invoke, Toggle, ...) |
| `set_value` | Установить значение (текст/слайдер) |

## Архитектура

```
computer-use-windows/
├── computer_use_windows/
│   ├── __init__.py
│   ├── cli.py              # CLI (mcp, doctor, screenshot, windows, apps)
│   ├── core/__init__.py    # Типы: Bounds, WindowInfo, AccessibilityNode, etc.
│   ├── interface/__init__.py  # WindowsInterface: Win32 API бэкенд
│   └── server/__init__.py  # MCP-сервер (stdio)
├── pyproject.toml
├── README.md
└── install.ps1
```

### Технологический стек

| Слой | Технология |
|------|-----------|
| Скриншоты | DXGI Desktop Duplication (`dxcam`) → GDI `BitBlt` |
| Ввод мыши | `SendInput` + `SetCursorPos` |
| Клавиатура | `SendInput` (KEYBDINPUT + KEYEVENTF_UNICODE) |
| Окна | `EnumWindows`, `SetForegroundWindow` |
| Accessibility | UIA COM (`uiautomation`) — всегда активно на Windows |
| MCP транспорт | `mcp` library, stdio |

## Отличия от cua

| | `cua` (trycua/cua) | `computer-use-windows` |
|---|---|---|
| **Архитектура** | Клиент-сервер через WebSocket | Локальный, прямой Win32 API |
| **Установка** | Docker / Lume / облако | `pip install` |
| **Зависимости** | `cua-core` + `cua-computer` + `cua-agent` | Только `pywin32` + `uiautomation` + `Pillow` |
| **Скриншоты** | Через WebSocket API | Прямой DXGI/GDI |
| **UIA** | Через WebSocket | Прямой COM |
| **MCP** | `cua-mcp-server` (FastMCP) | Свой MCP-сервер (stdlib mcp) |

## Безопасность

- **Нет сети.** Бинарные данные не покидают машину. MCP через stdio.
- **Локальный доступ.** `SendInput` требует интерактивный desktop.
- **UIA всегда включён.** В отличие от Linux AT-SPI, Windows accessibility не требует настройки.
- **Явные мутирующие тулы.** `click`, `drag`, `type_text` аннотированы как `destructive=true`.

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `pywin32` не установлен | `pip install pywin32` |
| `uiautomation` не установлен | `pip install uiautomation` |
| Скриншоты чёрные | Установите `dxcam`: `pip install dxcam` |
| DXGI не работает | Автоматический fallback на GDI `BitBlt` |
| `SendInput` игнорируется | Процесс должен быть на интерактивном desktop (не service) |

## Лицензия

MIT — см. [LICENSE](LICENSE).

Адаптировано из [trycua/cua](https://github.com/trycua/cua) (MIT License).
