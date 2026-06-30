# Install script for computer-use-windows
# Requires: Python 3.12+, Windows 10+
# Run: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [switch]$Dev,
    [switch]$WithDxgi,
    [switch]$User
)

$ErrorActionPreference = "Stop"
Write-Host "=== computer-use-windows installer ===" -ForegroundColor Cyan

# Check Python
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Python not found. Install Python 3.12+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Windows version
$osVersion = [Environment]::OSVersion.Version
if ($osVersion.Major -lt 10) {
    Write-Host "[WARN] Windows 10+ recommended. You're on $osVersion" -ForegroundColor Yellow
} else {
    Write-Host "[OK] Windows $($osVersion.Major)" -ForegroundColor Green
}

# Install package
Write-Host "Installing computer-use-windows..." -ForegroundColor Cyan

$pipArgs = @("install", "computer-use-windows")
if ($User) { $pipArgs += "--user" }

python -m pip @pipArgs

if ($Dev) {
    Write-Host "Installing dev dependencies..." -ForegroundColor Cyan
    python -m pip install computer-use-windows[dev] @(if ($User) { "--user" } else {})
}

if ($WithDxgi) {
    Write-Host "Installing DXGI support (dxcam)..." -ForegroundColor Cyan
    python -m pip install computer-use-windows[dxgi] @(if ($User) { "--user" } else {})
}

# Verify installation
Write-Host "`nVerifying installation..." -ForegroundColor Cyan
computer-use-windows doctor

Write-Host "`n=== Installation complete ===" -ForegroundColor Green
Write-Host "`nUsage:" -ForegroundColor White
Write-Host "  computer-use-windows mcp       # Start MCP server" -ForegroundColor Gray
Write-Host "  computer-use-windows doctor    # Readiness report" -ForegroundColor Gray
Write-Host "  computer-use-windows screenshot # Capture screen" -ForegroundColor Gray
