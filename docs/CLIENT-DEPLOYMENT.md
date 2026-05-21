# Store PC deployment (Windows)

Public repository: [https://github.com/Pereyra3/Ferret-web](https://github.com/Pereyra3/Ferret-web)

**Local URL (after setup):** [http://ferreteriapena/](http://ferreteriapena/) on port **80** (no `:8000` in the address bar).

---

## GitHub version

If the repo on GitHub still shows the old `store_ops` layout, push the current code from your dev machine first (`core`, `warehouse`, `sales`):

```powershell
git add .
git commit -m "Update structure for store deployment"
git push origin main
```

Install on the store PC only after GitHub matches this project layout.

---

## 1. Prerequisites (one time)

1. **Python 3.11+** — [python.org/downloads](https://www.python.org/downloads/) — check **Add to PATH**.
2. **Git** — [git-scm.com/download/win](https://git-scm.com/download/win)

---

## 2. Download the code

Open **PowerShell** (public repo; no GitHub account required to clone):

```powershell
cd C:\
git clone https://github.com/Pereyra3/Ferret-web.git
cd Ferret-web
```

Without Git: GitHub → **Code** → **Download ZIP**, extract to `C:\Ferret-web`.

---

## 3. Install the application

```powershell
cd C:\Ferret-web
powershell -ExecutionPolicy Bypass -File .\scripts\install-cliente.ps1
python manage.py createsuperuser
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py setup_defaults
python manage.py setup_roles --demo-users
```

The install script sets `DJANGO_ALLOWED_HOSTS` to include **`ferreteriapena`**.

---

## 4. Friendly hostname (`ferreteriapena`)

Maps the name to this PC in the Windows hosts file (run **PowerShell as Administrator**):

```powershell
cd C:\Ferret-web
powershell -ExecutionPolicy Bypass -File .\scripts\setup-hostname.ps1
```

Adds: `127.0.0.1 ferreteriapena`

Then open: **http://ferreteriapena/**

On **other PCs** on the LAN, add the same line with the **store PC’s IP** instead of `127.0.0.1`, for example:

```
192.168.1.50 ferreteriapena
```

---

## 5. Port 80 (standard HTTP)

Windows only allows port **80** for processes started with **administrator** rights.

**Manual test (Administrator PowerShell):**

```powershell
cd C:\Ferret-web
.\.venv\Scripts\Activate.ps1
python manage.py runserver ferreteriapena:80
```

Open: **http://ferreteriapena/**

If you see “permission denied” on port 80, run PowerShell as Administrator, or check that **IIS / World Wide Web Publishing Service** is stopped (it also uses port 80):

```powershell
Get-Service W3SVC
Stop-Service W3SVC
Set-Service W3SVC -StartupType Disabled
```

---

## 6. Start automatically when the PC boots / user logs on

Register the scheduled task (**run PowerShell as Administrator** so port 80 works):

```powershell
cd C:\Ferret-web
powershell -ExecutionPolicy Bypass -File .\scripts\setup-hostname.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\registrar-tarea-inicio.ps1
```

Creates task **FerreteriaWeb** (runs at **log on**, with highest privileges for port 80).

**Test without reboot:**

```powershell
schtasks /Run /TN "FerreteriaWeb"
```

Wait a few seconds, then open **http://ferreteriapena/**

**Remove the task:**

```powershell
schtasks /Delete /TN "FerreteriaWeb" /F
```

**Logs:** `C:\Ferret-web\logs\servidor-YYYY-MM-DD.log`

### Start at boot (before logon)

Only if the PC uses **automatic logon** for a fixed store user. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\registrar-tarea-inicio.ps1 -AlIniciarSesion:$false
```

---

## 7. Demo users

After `setup_roles --demo-users`:

| Username  | Password  | Role       |
|-----------|-----------|------------|
| demo      | demo      | Cashier    |
| encargado | encargado | Supervisor |
| gerente   | gerente   | Manager    |

In **Admin** (`http://ferreteriapena/admin/`): create **suppliers**, assign users to stores (**Stores → Assigned users**).

---

## 8. Backups

Copy regularly:

- `C:\Ferret-web\data\db.sqlite3`
- `C:\Ferret-web\exports\`

---

## 9. Update from GitHub

```powershell
cd C:\Ferret-web
git pull
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
```

Do **not** delete `data\db.sqlite3` if you need to keep sales and inventory.

---

## 10. LAN access (optional)

1. On the store PC, note its IP (`ipconfig`), e.g. `192.168.1.50`.
2. In `.env`:

   ```
   DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,ferreteriapena,192.168.1.50
   ```

3. Start listening on all interfaces (**Administrator**):

   ```powershell
   python manage.py runserver 0.0.0.0:80
   ```

4. On other PCs, add to hosts: `192.168.1.50 ferreteriapena` and open **http://ferreteriapena/**

---

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Port 80 in use | Stop IIS (`W3SVC`) or Skype/other app using port 80 |
| `DisallowedHost` | Add hostname/IP to `DJANGO_ALLOWED_HOSTS` in `.env` |
| Name does not resolve | Run `setup-hostname.ps1` as Administrator |
| Task runs but page down | Check `logs\servidor-*.log`, run task as Administrator |
