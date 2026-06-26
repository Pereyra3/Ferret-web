# Allows inbound HTTP (TCP 80) so other PCs on the store LAN can reach the app.
# Run as Administrator. Safe to run multiple times (rule is recreated).
param(
    [int]$Port = 80,
    [string]$RuleName = "Ferreteria Web (HTTP 80)"
)

$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Error "Run PowerShell as Administrator to change the firewall."
}

Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile Any `
    -Description "Inbound HTTP for the Ferreteria store app (waitress on port $Port)." | Out-Null

Write-Host "Firewall rule '$RuleName' created for inbound TCP $Port (all profiles)." -ForegroundColor Green
Write-Host "Other PCs can now reach this PC on port $Port over the LAN."
