# Instalación inicial en PC del cliente (Windows PowerShell)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== Ferretería — instalación en $ProjectRoot ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python no está instalado o no está en PATH. Instale Python 3.11+ desde https://www.python.org/downloads/"
}

$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Python: $pyVersion"

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "Creando entorno virtual..."
    python -m venv .venv
}

Write-Host "Activando entorno e instalando dependencias..."
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Yellow
}
# Ensure store hostname is allowed (http://ferreteriapena/)
$envPath = Join-Path $ProjectRoot ".env"
$content = Get-Content $envPath -Raw
if ($content -notmatch "ferreteriapena") {
    $content = $content -replace "DJANGO_ALLOWED_HOSTS=.*", "DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,ferreteriapena"
    Set-Content -Path $envPath -Value $content.TrimEnd() -NoNewline
    Add-Content -Path $envPath -Value "`n"
}

Write-Host "Migraciones y datos iniciales..."
python manage.py migrate
python manage.py setup_defaults
python manage.py setup_roles --demo-users

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Green
Write-Host "Optional: python manage.py createsuperuser"
Write-Host "Optional: python manage.py seed_demo"
Write-Host "Hostname:  powershell -ExecutionPolicy Bypass -File .\scripts\setup-hostname.ps1  (as Admin)"
Write-Host "Test:      python manage.py runserver ferreteriapena:80  (as Admin)"
Write-Host "Auto-start: powershell -ExecutionPolicy Bypass -File .\scripts\registrar-tarea-inicio.ps1  (as Admin)"
Write-Host "Open:      http://ferreteriapena/"
