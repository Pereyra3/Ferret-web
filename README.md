# Ferretería — internal web app (Django)

Operations panel for **one store initially** (multi-branch ready via `Store` / `store_id`). Daily work: **products, sales, supplier purchases, supplier payments, inventory, and profit dashboard**. **End-of-day (EOD)** exports **sales only** as PDF and CSV for transcription into the corporate system; it does **not** export inventory to the legacy system.

## Requirements

- Python 3.11+ recommended  
- Windows 11 / modest PC: SQLite by default (low RAM). PostgreSQL optional later.

## Quick start

```powershell
cd ferreteria-web
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py setup_defaults
python manage.py setup_roles --demo-users
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in. In **Admin** (`/admin/`), create **suppliers** before recording purchases or payments.

### Demo data (optional)

Borra datos operativos y carga catálogo, inventario, compras, ventas y cierres de los últimos 30 días:

```powershell
python manage.py seed_demo
```

Usuario mínimo (tienda + roles + `demo` / `demo` como **Cajero**):

```powershell
python manage.py setup_defaults
python manage.py setup_roles --demo-users
```

Usuarios de prueba con `--demo-users`: `demo` (Cajero), `encargado` / `encargado`, `gerente` / `gerente` (staff + Admin).

## Business rule (single source of truth)

While this app is the main daily system, **avoid entering the same day’s sales in the old system** to prevent duplicate figures. The legacy system is fed at close of day via **assisted transcription** (PDF/CSV) or, later, RPA for **sales only**.

## End of day (EOD)

- **Web:** menu **Cierre día**.  
- **CLI (Windows Task Scheduler):**

```powershell
cd ferreteria-web
.\.venv\Scripts\Activate.ps1
python manage.py eod_export --date 2026-05-13
python manage.py eod_export --date 2026-05-13 --force
```

Files are written under the project `exports/` folder (or `EOD_EXPORT_DIR` in `.env`).

### Thermal receipt tickets (handheld printer)

- **Daily sales:** **Cierre día** → **Imprimir ticket del día** (uses the date in the form). Opens a narrow ticket and triggers the browser print dialog (`?auto=1`). Choose your USB/Bluetooth thermal printer in the dialog.
- **Suggested inventory:** **Inventario** → **Inventario sugerido al máximo** → **Imprimir ticket**.

Direct URLs (must be signed in): `/cierre/imprimir-ticket/?date=YYYY-MM-DD`, `/inventario/imprimir-sugerido/`. Add `&auto=1` to open the print dialog immediately.

Configure the thermal printer once in Windows as the default (or select it in the print dialog). Paper width: layout targets **80 mm** (~58 mm works with smaller margins).

## Profit dashboard

`/dashboard/` shows **real profit**: confirmed sales minus supplier payments (cash flow), plus purchases registered in the period for operating margin. Charts support day / month / year grouping.

## Multi-store

Add branches in **Admin → Stores** and assign each user under **Assigned users** (or from the user’s store list in Admin). Users only see data for their assigned branches; **superusers** see every store.

If a user has **one** assigned store, lists and forms are scoped to that branch automatically (no filter UI). With **two or more** assignments, the app bar store link opens `/tiendas/seleccion/` to filter **all assigned**, **one**, or **several** for lists, inventory, and the profit dashboard.

New sales, purchases, supplier payments, stock adjustments, and EOD close use the **write store**: the only selected branch among the filter, or the first assigned / default store when several are visible.

## Roles (Cajero / Encargado / Gerente)

Django groups use default model permissions (`python manage.py setup_roles`):

| Rol | Panel | Admin `/admin/` |
|-----|--------|-----------------|
| **Cajero** | Ventas, consulta producto/stock | No |
| **Encargado** | + inventario, compras, pagos proveedor, ganancias | No |
| **Gerente** | Todo + cierre día + filtro de tiendas | Sí (`is_staff`) |

Assign users in Admin → Users → Groups.

## Transferencias e importación Excel

- **Transferencias** (`/inventario/transferencias/`): solicitudes pendientes; la tienda destino **acepta o rechaza** (`warehouse.change_stocktransfer` + usuario asignado a esa sucursal). El stock se mueve solo al aceptar.
- **Nueva transferencia** (`/inventario/transferencia/`): crea la solicitud (`warehouse.add_stocktransfer`). Valida stock en origen al aceptar.
- **Importar inventario** (`/inventario/importar/`): archivo `.xlsx` con columnas `sku` (o `código`) y `cantidad` (o `existencia`). Modos: **fijar existencia** o **sumar al actual**. Aplica a la **tienda de trabajo** del filtro de sucursales.
- Plantilla de ejemplo: `/inventario/importar/plantilla.xlsx`

Tras migrar: `python manage.py setup_roles` (permisos nuevos en Encargado).

## GitHub (personal repo)

1. Create a **private** repository on GitHub.  
2. In the project folder: `git init`, `git remote add origin ...`, `git add`, `git commit`, `git push`.  
3. Enable **2FA** on GitHub; do not commit `.env`. Code in Git **does not replace** database backups (`data/db.sqlite3` or dumps).

## RPA (Playwright / Selenium)

Optional and **for legacy sales screens only**; do **not** automate inventory in the old system. Keep PDF/CSV as fallback.

## Deployment on the store PC

Public repo: [github.com/Pereyra3/Ferret-web](https://github.com/Pereyra3/Ferret-web)

**Store PC guide (clone, install, auto-start, `http://ferreteriapena/` on port 80):** [`docs/CLIENT-DEPLOYMENT.md`](docs/CLIENT-DEPLOYMENT.md)

Quick setup on the store PC (**Administrator** PowerShell for hostname + port 80):

```powershell
git clone https://github.com/Pereyra3/Ferret-web.git
cd Ferret-web
powershell -ExecutionPolicy Bypass -File .\scripts\install-cliente.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup-hostname.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\registrar-tarea-inicio.ps1
```

- Service with **NSSM** or **PM2** running `waitress` / `gunicorn` + `collectstatic`, or `runserver` for tests only.  
- Scheduled copy of `data/db.sqlite3` and `exports/`.  
- Avoid Docker Desktop plus many apps on **8 GB RAM** in the same session.

## Project layout (aligned with tech_tool)

Django apps are split by domain; `ferreteria/urls.py` mounts each app (HTML routes at the root, REST under `api/store/`):

| App | Role |
|-----|------|
| **core** | Shared `Store`, login shell, home, profit dashboard, `DefaultStoreMiddleware` |
| **warehouse** | Products, stock, supplier purchases/payments, inventory UI |
| **sales** | POS sales (draft → checkout), EOD export, sale tickets |

```
ferreteria-web/
├── core/           models, views/, templates/core/, static/core/
├── warehouse/      models, views, forms, services/, api/, templates/warehouse/
├── sales/          models, views, forms, services/, templates/sales/
└── ferreteria/     settings, urls
```

Existing SQLite tables keep the `store_ops_*` names via `Meta.db_table` (no data migration needed after `--fake-initial` on a DB that already ran `store_ops` migrations).

## Tests

Uses **pytest** and **pytest-django**. Tests live under `core/tests/`, `warehouse/tests/`, and `sales/tests/`.

```powershell
pip install -r requirements.txt
pytest
```

Each line shows **file → class → test** (like tech_tool), e.g.  
`warehouse/tests/test_views.py::TestLoginRequired::test_home_requires_login PASSED [  1%]`

Run a single **class** or **test** (faster, no need to skip coverage manually):

```powershell
pytest core/tests/test_roles.py::TestRolePermissions -v
pytest warehouse/tests/test_views.py::TestAuthenticatedViews::test_sale_list -v
pytest -k "TestRolePermissions" -v
```

List tests without running:

```powershell
pytest --collect-only -q
```

Coverage is enforced at **100%** on each app’s `models.py` and `views.py` (`.coveragerc`):

```powershell
pytest --cov-report=html
```

Quick iteration without coverage report:

```powershell
pytest core/tests/test_money.py -v --no-cov
```

## UI language

Store-facing templates and messages are **Spanish** (`es-es`). Developer-facing code comments, management commands, and Django admin field labels are **English**.
