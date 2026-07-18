# Computer Use Windows — Installation Script
# Run: powershell -ExecutionPolicy Bypass -File install.ps1
# Optional: powershell -ExecutionPolicy Bypass -File install.ps1 -UIA -Remote

param(
    [switch]$UIA = $false,
    [switch]$Remote = $false,
    [switch]$Dev = $false
)

Write-Host "=== Computer Use Windows v2.0.0 Installer ===" -ForegroundColor Cyan

# Check Python
try {
    $pyVer = python --version 2>&1
    Write-Host "Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found. Install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Install from GitHub
Write-Host "Installing computer-use-windows from GitHub..." -ForegroundColor Cyan

if ($Dev) {
    # Dev install: clone and editable install
    $repoUrl = "https://github.com/sbrejnev988-coder/computer-use-windows.git"
    $installDir = "$env:USERPROFILE\computer-use-windows"
    
    if (Test-Path $installDir) {
        Write-Host "Directory $installDir exists, updating..." -ForegroundColor Yellow
        Set-Location $installDir
        git pull
    } else {
        git clone $repoUrl $installDir
        Set-Location $installDir
    }
    pip install -e ".[win32]"
} else {
    # Direct install from GitHub
    pip install "git+https://github.com/sbrejnev988-coder/computer-use-windows.git#egg=computer-use-windows&subdirectory="
    pip install pywin32 psutil pynput
}

# Optional: UI Automation
if ($UIA) {
    Write-Host "Installing UI Automation support (uiautomation)..." -ForegroundColor Cyan
    pip install uiautomation
}

# Optional: Remote WebSocket server
if ($Remote) {
    Write-Host "Installing remote server support (websockets)..." -ForegroundColor Cyan
    pip install websockets
}

# Verify installation
Write-Host "`nVerifying installation..." -ForegroundColor Cyan
python -c "import computer_use_windows; print('computer-use-windows imported OK')"
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Installation Complete ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  computer-use-windows mcp       # Local MCP server (stdio)" -ForegroundColor Gray
    Write-Host "  computer-use-windows remote    # WebSocket remote server" -ForegroundColor Gray
    Write-Host "  computer-use-windows doctor    # Diagnostics" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Env vars:" -ForegroundColor White
    Write-Host "  COMPUTER_USE_WINDOWS_TOKEN     # Auth token for remote mode" -ForegroundColor Gray
    Write-Host "  COMPUTER_USE_WINDOWS_PROFILE   # Capability profile (desktop/admin/unsafe)" -ForegroundColor Gray
} else {
    Write-Host "ERROR: Import verification failed" -ForegroundColor Red
    exit 1
}
