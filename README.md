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
python manage.py makemigrations store_ops
python manage.py migrate
python manage.py setup_defaults
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in. In **Admin** (`/admin/`), create **suppliers** before recording purchases or payments.

### Demo data (optional)

```powershell
python manage.py seed_demo
python manage.py seed_demo_sales
python manage.py seed_demo_payments
```

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

## Profit dashboard

`/dashboard/` shows **real profit**: confirmed sales minus supplier payments (cash flow), plus purchases registered in the period for operating margin. Charts support day / month / year grouping.

## Multi-store (later)

The UI uses the **default store** (`DEFAULT_STORE_CODE`, usually `principal`). For a second branch: add another `Store` in admin; later add store selector and per-location permissions.

## GitHub (personal repo)

1. Create a **private** repository on GitHub.  
2. In the project folder: `git init`, `git remote add origin ...`, `git add`, `git commit`, `git push`.  
3. Enable **2FA** on GitHub; do not commit `.env`. Code in Git **does not replace** database backups (`data/db.sqlite3` or dumps).

## RPA (Playwright / Selenium)

Optional and **for legacy sales screens only**; do **not** automate inventory in the old system. Keep PDF/CSV as fallback.

## Deployment on the store PC

- Service with **NSSM** or **PM2** running `waitress` / `gunicorn` + `collectstatic`, or `runserver` for tests only.  
- Scheduled copy of `data/db.sqlite3` and `exports/`.  
- Avoid Docker Desktop plus many apps on **8 GB RAM** in the same session.

## Tests

Uses **pytest** and **pytest-django**. Tests live in `store_ops/tests/`:

- `test_models.py` — `store_ops/models.py`
- `test_views.py` — `store_ops/views.py` (HTTP + helpers)

```powershell
pip install -r requirements.txt
pytest
```

Coverage is enforced at **100%** on `models.py` and `views.py` only (`.coveragerc`):

```powershell
pytest --cov-report=html
```

## UI language

Store-facing templates and messages are **Spanish** (`es-es`). Developer-facing code comments, management commands, and Django admin field labels are **English**.
