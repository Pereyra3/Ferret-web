# Production server: serves Django via waitress (WSGI) on port 80, all interfaces.
# Static files are served by WhiteNoise. Requires admin rights for port 80.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
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
    Write-Log "Starting Ferreteria (production/waitress) at $ProjectRoot on port $Port"
    if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
        Write-Log "ERROR: .venv missing. Run scripts\install-cliente.ps1"
        exit 1
    }
    & .\.venv\Scripts\Activate.ps1
    Start-Sleep -Seconds 5
    Write-Log "collectstatic"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    python manage.py collectstatic --noinput 2>&1 | ForEach-Object { Write-Log "$_" }
    Write-Log "waitress-serve --listen=*:$Port ferreteria.wsgi:application"
    python -m waitress --listen="*:$Port" ferreteria.wsgi:application 2>&1 | ForEach-Object { Write-Log "$_" }
    $ErrorActionPreference = $prevEap
}
catch {
    Write-Log "ERROR: $_"
    exit 1
}
