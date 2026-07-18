# Computer Use Windows v2.1.2 — Installation Script
# Run: powershell -ExecutionPolicy Bypass -File install.ps1 [-UIA] [-Remote] [-Dev]

param(
    [switch]$UIA = $false,
    [switch]$Remote = $false,
    [switch]$Dev = $false
)

Write-Host "=== Computer Use Windows v2.1.2 Installer ===" -ForegroundColor Cyan

try {
    $pyVer = python --version 2>&1
    Write-Host "Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python 3.11+ required" -ForegroundColor Red
    exit 1
}

$repoUrl = "https://github.com/sbrejnev988-coder/computer-use-windows.git"

if ($Dev) {
    Write-Host "Dev install from GitHub..." -ForegroundColor Cyan
    $installDir = "$env:USERPROFILE\computer-use-windows"
    if (Test-Path $installDir) {
        Set-Location $installDir
        git pull
    } else {
        git clone $repoUrl $installDir
        Set-Location $installDir
    }
    pip install -e "."
} else {
    Write-Host "Installing from GitHub..." -ForegroundColor Cyan
    pip install "git+$repoUrl"
}

# Dependencies are auto-installed via pyproject.toml conditional deps

if ($UIA) {
    Write-Host "Installing UI Automation..." -ForegroundColor Cyan
    pip install uiautomation
}

if ($Remote) {
    Write-Host "Installing remote server..." -ForegroundColor Cyan
    pip install websockets
}

# Smoke test
Write-Host "`nSmoke test — MCP server creation..." -ForegroundColor Cyan
$smoke = @'
import asyncio, sys
from computer_use_windows.server import create_server

async def check():
    server = create_server()
    tools = await server.get_tools()
    assert len(tools) >= 60, f"Expected >=60 tools, got {len(tools)}"
    print(f"MCP OK: {len(tools)} tools registered")
    return 0

sys.exit(asyncio.run(check()))
'@

$smoke | python - 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Installation Complete ===" -ForegroundColor Green
    Write-Host "Usage:" -ForegroundColor White
    Write-Host "  computer-use-windows mcp       # Local MCP server" -ForegroundColor Gray
    Write-Host "  computer-use-windows remote    # WebSocket server" -ForegroundColor Gray
    Write-Host "  computer-use-windows doctor    # Diagnostics" -ForegroundColor Gray
} else {
    Write-Host "`nWARNING: Smoke test failed. Run 'computer-use-windows doctor' for details." -ForegroundColor Yellow
}
