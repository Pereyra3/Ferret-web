# Ferretería — aplicación web interna (Django)

Panel para **una tienda al inicio** (multi-sucursal preparado en modelo de datos con `store_id` / `Store`). Operación diaria: **productos, ventas, compras a proveedor, pagos a proveedor, inventario y dashboards**. El **cierre (EOD)** genera **solo ventas** en PDF y CSV para transcribir al sistema corporativo; **no** exporta movimientos de inventario al legado.

## Requisitos

- Python 3.11+ recomendado  
- Windows 11 / PC modesto: SQLite por defecto (poca RAM). Opcional: PostgreSQL más adelante.

## Instalación rápida

```powershell
cd ferreteria-web
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations store_ops
python manage.py migrate
python manage.py setup_defaults
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://127.0.0.1:8000/` e inicie sesión. En **Admin** (`/admin/`) cree **proveedores** antes de registrar compras o pagos.

## Regla de negocio (una sola fuente)

Mientras usen esta app como operación principal, **eviten registrar las mismas ventas el mismo día en el sistema viejo** para no duplicar cifras. El sistema viejo queda alimentado al cierre con **transcripción asistida** (PDF/CSV) o, más adelante, RPA **solo de ventas**.

## Cierre del día (EOD)

- **Web:** menú **Cierre día**.  
- **Consola (Programador de tareas de Windows):**

```powershell
cd ferreteria-web
.\.venv\Scripts\Activate.ps1
python manage.py eod_export --date 2026-05-13
python manage.py eod_export --date 2026-05-13 --force
```

Los archivos salen en la carpeta `exports/` del proyecto (o la ruta de `EOD_EXPORT_DIR` en `.env`).

## Dashboards

- Ventas agregadas por **día / mes / año** (selector en pantalla).  
- **Proveedores:** saldo estimado (compras − pagos + saldo inicial).  
- **Productos:** unidades vendidas en el rango de fechas.

## Multi-sucursal (fase posterior)

Hoy la UI usa la tienda **por defecto** (`DEFAULT_STORE_CODE`, típicamente `principal`). Para segunda tienda: crear otra fila `Store` en admin, más adelante selector de contexto y permisos por local.

## GitHub (repo personal)

1. Cree un repositorio **privado** en GitHub.  
2. En la carpeta del proyecto: `git init`, `git remote add origin ...`, `git add`, `git commit`, `git push`.  
3. Active **2FA** en GitHub; no suba `.env`. El código en Git **no sustituye** backups de la base de datos (`data/db.sqlite3` o dumps).

## RPA (Playwright / Selenium)

Opcional y **solo para pantallas de ventas** del sistema web viejo; **no** automatizar inventario en el legado. Mantener el PDF/CSV como respaldo.

## Despliegue en el PC de la ferretería

- Servicio con **NSSM** o **PM2** ejecutando `gunicorn`/`waitress` + `collectstatic`, o `runserver` solo en pruebas.  
- Copia programada de `data/db.sqlite3` y de `exports/`.  
- Evite Docker Desktop + muchas apps en **8 GB RAM** en la misma sesión.

## Inspiración “TechTool”

Interfaz tipo herramienta interna: **Django + plantillas + Bootstrap + Chart.js**, sin SPA obligatoria, fácil de mantener en equipo pequeño.
