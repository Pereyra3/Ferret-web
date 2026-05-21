# Maps ferreteriapena -> 127.0.0.1 in the Windows hosts file (requires Administrator)
param(
    [string]$HostName = "ferreteriapena",
    [string]$IpAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$hostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Error "Run PowerShell as Administrator to update the hosts file."
}

$content = Get-Content $hostsPath -Raw
$pattern = [regex]::Escape($HostName)
if ($content -match "(?m)^\s*\d+\.\d+\.\d+\.\d+\s+$pattern\s*$") {
    Write-Host "Hosts file already contains $HostName." -ForegroundColor Yellow
    exit 0
}

$line = "$IpAddress`t$HostName"
Add-Content -Path $hostsPath -Value "`n# Ferreteria store app`n$line" -Encoding ASCII
Write-Host "Added: $line" -ForegroundColor Green
Write-Host "Open:  http://$HostName/" -ForegroundColor Cyan
