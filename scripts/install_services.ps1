<#
Install services for lucenera on Windows (requires Administrator).

This script attempts to install cloudflared as a service and then
install the Python launcher (`start_lucenera.py`) as a Windows service
using NSSM if available. It does NOT download NSSM for you. Run this
script from an elevated PowerShell prompt.

Usage (Admin PowerShell):
  PS> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  PS> .\scripts\install_services.ps1

Notes:
- cloudflared: if 'cloudflared' is in PATH, the script runs `cloudflared service install`.
- If the host doesn't have NSSM, the script will print the NSSM steps to run manually.
#>

function Is-Administrator {
    $current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Is-Administrator)) {
    Write-Host "This script must be run as Administrator. Open PowerShell as Administrator and re-run." -ForegroundColor Yellow
    exit 1
}

$workspace = (Get-Location).Path
$venvPy = Join-Path $workspace ".venv\Scripts\python.exe"
$launcher = Join-Path $workspace "start_lucenera.py"

Write-Host "Workspace: $workspace"

Write-Host "-- Installing cloudflared service (if cloudflared is in PATH) --"
try {
    $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cf) {
        Write-Host "Found cloudflared: $($cf.Path) — running 'cloudflared service install'"
        & cloudflared service install
        Write-Host "cloudflared service install returned. Check Windows Services (services.msc) for 'cloudflared' or run: Get-Service cloudflared" -ForegroundColor Green
    } else {
        Write-Host "cloudflared not found in PATH. Install cloudflared and re-run this script, or run manually: cloudflared service install" -ForegroundColor Yellow
    }
} catch {
    Write-Host "cloudflared install failed: $_" -ForegroundColor Red
}

Write-Host "`n-- Installing lucenera service (via NSSM recommended) --"
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if ($nssm) {
    Write-Host "Found nssm: $($nssm.Path) — installing service 'lucenera' using NSSM"
    $svcName = "lucenera"
    & nssm install $svcName $venvPy $launcher
    & nssm set $svcName AppDirectory $workspace
    & nssm set $svcName Start SERVICE_AUTO_START
    Write-Host "Starting service..."
    & nssm start $svcName
    Write-Host "Service '$svcName' installed and started via nssm." -ForegroundColor Green
} else {
    Write-Host "NSSM not found in PATH. You can download NSSM from https://nssm.cc/download and place nssm.exe in your PATH." -ForegroundColor Yellow
    Write-Host "Manual NSSM example commands to run as Admin after installing NSSM:"
    Write-Host "nssm install lucenera \"$venvPy\" \"$launcher\"" -ForegroundColor Cyan
    Write-Host "nssm set lucenera AppDirectory \"$workspace\"" -ForegroundColor Cyan
    Write-Host "nssm set lucenera Start SERVICE_AUTO_START" -ForegroundColor Cyan
    Write-Host "nssm start lucenera" -ForegroundColor Cyan
}

Write-Host "\n-- Done. Verify: Get-Service cloudflared; Get-Service lucenera (or check services.msc)." -ForegroundColor Green
