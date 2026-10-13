# IPMS Risk Component — Installation Guide (A–Z)

**Predictive Risk Monitoring & Contribution Analytics** — complete setup from a clean
machine to a running system. Follow the steps in order.

---

## A. What you are installing

Two applications that share one database:

| App | Tech | Port | What it's for |
|---|---|---|---|
| **Backend + management UI** | Python / FastAPI | **8000** | The API, ML risk prediction, GitHub/Jira integration, risk emails, and an HTML management UI (member add/remove, etc.) |
| **Frontend** | React / Vite | **5173** | The main UI: login → projects → live project analytics, project creation, Excel team upload |

Folder layout inside `component_risk/`:

```
component_risk/
├── ipms-risk-app/        ← backend (FastAPI) + trained ML model + .env
│   ├── main.py, auth.py, database.py, contribution.py, jira_client.py,
│   │   emailer.py, risk_monitor.py, bulk_upload.py
│   ├── best_risk_prediction_model.pkl, scaler.pkl
│   ├── scripts/jira_demo_setup.py
│   └── templates/, static/
├── frontend/             ← React app (Vite)
├── data/, models/, notebooks/, results/, trained_data/   ← ML training assets
├── requirements.txt
└── INSTALLATION.md       ← this file
```

---

## B. Prerequisites

Install these first (all free):

| Software | Version | Get it from | Check with |
|---|---|---|---|
| Python | 3.11+ | https://www.python.org/downloads/ | `python --version` |
| Node.js (includes npm) | 20+ | https://nodejs.org/ | `node --version` |
| Git | any recent | https://git-scm.com/ | `git --version` |

> On Windows, tick **"Add Python to PATH"** during the Python install.

---

## C. Get the code

```bash
git clone <your-repo-url> R26-IT-095
```

```bash
cd R26-IT-095/component_risk
```

(Or check out the branch: `git checkout Predictive-Risk-Monitoring-and-Contribution-Analytics_v2`)

---

## D. Backend setup (Python)

### D1. Create a virtual environment

From the `component_risk` folder:

```bash
python -m venv .venv
```

Activate it — **Windows (PowerShell):**

```bash
.venv\Scripts\Activate.ps1
```

**Windows (cmd):** `.venv\Scripts\activate.bat` · **macOS/Linux:** `source .venv/bin/activate`

### D2. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, uvicorn, scikit-learn, pandas, openpyxl, python-dotenv and friends
(~2–3 minutes).

---

## E. Configuration — the `.env` file

Create a file named `.env` **inside `ipms-risk-app/`** (next to `main.py`).
This file holds secrets — it is git-ignored and must **never** be committed.

```env
# ---- Jira (required for task/delivery analytics) ----------------------
JIRA_BASE_URL = "https://yourteam.atlassian.net"
JIRA_EMAIL = "you@example.com"
JIRA_API_TOKEN = "your-jira-api-token"

# ---- GitHub (strongly recommended) -------------------------------------
# Without this you get only 60 API requests/hour (one analysis uses ~15-25).
GITHUB_TOKEN = "ghp_your_personal_access_token"

# ---- Automatic risk emails (optional) -----------------------------------
# SMTP_HOST = "smtp.gmail.com"
# SMTP_PORT = "587"
# SMTP_USERNAME = "yourgmail@gmail.com"
# SMTP_PASSWORD = "your-16-char-app-password"
# SMTP_FROM = "yourgmail@gmail.com"
# APP_BASE_URL = "http://127.0.0.1:5175"
# RISK_CHECK_INTERVAL_MINUTES = "60"
# RISK_ALERT_COOLDOWN_HOURS = "24"
```

### How to get each token

- **Jira API token** — https://id.atlassian.com/manage-profile/security/api-tokens →
  *Create API token*. Use the same email you log into Jira with.
- **GitHub token** — https://github.com/settings/tokens → *Generate new token (classic)*.
  **No scopes needed** for public repositories. Gives 5,000 requests/hour instead of 60.
- **Gmail App Password** (only if you want automatic risk emails) — Google Account →
  Security → 2-Step Verification → *App passwords*. Uncomment the SMTP lines and fill them in.

Everything still works with an empty `.env` — Jira panels show a friendly
"not configured" message and emails stay off.

---

## F. Start the backend

From `component_risk` (with the venv active):

```bash
python -m uvicorn main:app --app-dir ipms-risk-app --port 5000
```

You should see `Uvicorn running on http://0.0.0.0:5000`.

- The SQLite database (`ipms-risk-app/ipms.db`) is **created automatically** on first run.
- Quick check: open http://localhost:5000/api/health — it should return `status: ok`.

---

## G. Frontend setup (React)

Open a **second terminal**:

```bash
cd R26-IT-095/component_risk/frontend
```

```bash
npm install
```

```bash
npm run dev
```

Open **http://localhost:5175** — the IPMS Risk login page appears.
(The dev server proxies all `/api` calls to the backend on port 5000, so both must be running.)

---

## H. First run — create accounts and a project

1. On http://localhost:5175 click **Create an account** → register a **Supervisor**
   (any email, password min 8 characters).
2. You land on **My Projects**. Create your first project:
   - **Create a Project** form (name, Team ID, GitHub repo URL, optional Jira key), **or**
   - **Bulk Upload Teams (Excel)** → *Download Template* → fill one row per member
     (Project ID, Project Name, Team Leader, Member Name, IT Number, IT Email,
     GitHub Username, Repo URL, Jira Key) → upload.
     Student accounts are created automatically — **first password = their IT number**.
3. Click the project card → the live analytics page loads (10–20 s the first time):
   ML risk prediction, alerts, KPIs, task status, 52-week commit chart,
   Contribution Index ranking, Jira task scores. Auto-refreshes every 60 s.
4. Students sign in with their own accounts and see **only their own team's** analytics.

---

## I. Optional — Jira demo data

To fill a Jira board with realistic demo tasks (mixed done/late/overdue):

```bash
python ipms-risk-app/scripts/jira_demo_setup.py
```

It creates a Jira project `IPMS` with 12 tasks using your `.env` credentials.

---

## J. Ports & URLs summary

| URL | What |
|---|---|
| http://localhost:5175 | Main UI (React) — isolated Risk login, projects, analytics, creation |
| http://localhost:5000 | Risk API and legacy management UI |
| http://localhost:5000/api/... | JSON API used by the React app |

---

## K. Resetting / uninstalling

- **Reset all data** (accounts, projects, alert history): stop the backend and delete
  `ipms-risk-app/ipms.db`. It is rebuilt empty on the next start.
- **Uninstall**: delete the folder. Nothing is installed system-wide except Python/Node.

---

## L. Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python with "Add to PATH" ticked; reopen the terminal |
| `Activate.ps1 cannot be loaded` (PowerShell) | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Frontend shows "Backend is unavailable" | Start the backend first (step F); both must run at the same time |
| Port 8000/5173 already in use | Stop the other program, or change `--port` / `vite.config.js` |
| GitHub metrics all 0 + rate-limit warning | Add `GITHUB_TOKEN` to `.env`, restart the backend |
| "Jira is not configured" / 401 | Check the three `JIRA_*` values; tokens can be revoked — make a fresh one |
| "No issues found in Jira project" | The key is wrong, or the board is empty — run the demo script (step I) |
| Risk emails not arriving | Fill the SMTP lines, restart, then test: sign in as supervisor and run `fetch('/api/test-email',{method:'POST'}).then(r=>r.json()).then(console.log)` in the browser console |
| Forgot a password | No reset flow yet — delete `ipms.db` (loses data) or register a new account |
| Analysis is slow (~20 s) | Normal — live GitHub/Jira API calls; results are cached for 2 minutes |

---

## M. Further documentation

| File | Contents |
|---|---|
| `ipms-risk-app/FUNCTIONS.md` | Every function explained in plain English |
| `ipms-risk-app/METRICS.md` | Exactly how every number is calculated |
| `ipms-risk-app/DEMO.md` | Step-by-step demo script |
| `ipms-risk-app/REQUIREMENTS_COMPARISON.md` | Proposal vs. what is built |
| `frontend/Readme.md` | Frontend-specific notes |
