# AGENTS.md

## Cursor Cloud specific instructions

### Product

**Ferret-web** (repo root `/workspace`) is a single Django monolith for hardware-store operations (POS, inventory, purchases, EOD). There is no separate frontend or Docker stack.

### Python environment

- Use Python **3.11+** (3.12 works). On Debian/Ubuntu cloud VMs, `python3-venv` must be installed once (`sudo apt install python3.12-venv`) before `python3 -m venv .venv`.
- Activate: `source .venv/bin/activate` (Linux) or `.\.venv\Scripts\Activate.ps1` (Windows).
- Dependencies: `pip install -r requirements.txt` (see `README.md` quick start).

### First-time database bootstrap (after migrate)

```bash
cp .env.example .env   # if .env missing
python manage.py migrate
python manage.py setup_defaults
python manage.py setup_roles --demo-users
```

Demo users: `demo`/`demo` (Cajero), `encargado`/`encargado`, `gerente`/`gerente`.

### Run the web app (development)

```bash
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Open `http://127.0.0.1:8000/`. Production store PCs use port 80 and hostname `ferreteriapena` (see `docs/CLIENT-DEPLOYMENT.md`); dev uses `:8000`.

### Tests

Full suite with 100% coverage gate on models/views:

```bash
source .venv/bin/activate
pytest
```

Fast iteration without coverage: `pytest path/to/test.py -v --no-cov`.

### Linting

No dedicated linter config in repo; `pytest` is the primary quality gate.

### Gotchas

- Django warns about missing `warehouse/static` in `STATICFILES_DIRS`; harmless for dev.
- `runserver` is for dev/tests only; store deployment uses waitress/NSSM (Windows).
- SQLite lives at `data/db.sqlite3`; no separate DB service to start.
- Optional richer demo data: `python manage.py seed_demo` (wipes operational data first).
