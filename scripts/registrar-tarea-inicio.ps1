# Registers a Windows scheduled task to start the app at logon (port 80 = highest privileges)
param(
    [string]$ProjectRoot = "",
    [switch]$AlIniciarSesion = $true,
    [string]$HostName = "ferreteriapena"
)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$ProjectRoot = (Resolve-Path $ProjectRoot).Path

$TaskName = "FerreteriaWeb"
$ScriptPath = Join-Path $ProjectRoot "scripts\iniciar-ferreteria.ps1"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

# Port 80 requires Administrator on Windows
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

if ($AlIniciarSesion) {
    $Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $Desc = "Starts Ferreteria Web at logon (http://$HostName/ on port 80)."
}
else {
    $Trigger = New-ScheduledTaskTrigger -AtStartup
    $Desc = "Starts Ferreteria Web at Windows startup (port 80)."
}

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description $Desc `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' registered (RunLevel: Highest for port 80)." -ForegroundColor Green
Write-Host "  Folder:  $ProjectRoot"
Write-Host "  Script:  $ScriptPath"
Write-Host ""
Write-Host "Hostname:  run scripts\setup-hostname.ps1 as Administrator if not done yet."
Write-Host "Test:      schtasks /Run /TN `"$TaskName`""
Write-Host "Open:      http://$HostName/"
Write-Host "Remove:    schtasks /Delete /TN `"$TaskName`" /F"
