# Starts Django on port 80 with hostname ferreteriapena (scheduled task / manual)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$HostName = "ferreteriapena"
$Port = 80
Set-Location $ProjectRoot

$LogDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}
$LogFile = Join-Path $LogDir "servidor-$(Get-Date -Format 'yyyy-MM-dd').log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $LogFile -Value $line
}

try {
    Write-Log "Starting Ferreteria at $ProjectRoot ($HostName`:$Port)"
    if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
        Write-Log "ERROR: .venv missing. Run scripts\install-cliente.ps1"
        exit 1
    }
    & .\.venv\Scripts\Activate.ps1
    Start-Sleep -Seconds 5
    Write-Log "runserver ${HostName}:$Port"
    python manage.py runserver "${HostName}:${Port}" 2>&1 | ForEach-Object { Write-Log $_ }
}
catch {
    Write-Log "ERROR: $_"
    exit 1
}
