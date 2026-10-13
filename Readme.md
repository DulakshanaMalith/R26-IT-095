# IPMS — Intelligent Project Management System

IPMS is a four-component research prototype for undergraduate project teams and academic staff. Each component runs as its own service so its dependencies, data, and decisions remain distinguishable. The scheduling service also provides the integrated local home/login page.

| Component | What it does | Backend | Frontend | Persistence |
| --- | --- | --- | --- | --- |
| [Adaptive Scheduling and Generative Project Planning](component_scheduling/) | Extracts proposal tasks, builds versioned Gantt schedules, balances member work, tracks document/GitHub evidence, and supports academic presentation scheduling. | FastAPI `127.0.0.1:8000` | Served by backend (`/home`) | PostgreSQL `ipms_scheduling` |
| [Automated Quality Assessment and Adaptive Mentorship](component_quality/) | Analyzes proposal text, retrieves feedback, estimates grading/readiness, and provides supervisor analytics. | FastAPI `127.0.0.1:9000` | React/Vite `127.0.0.1:5173` | PostgreSQL `researchpilot`; local model artifacts |
| [Predictive Risk Monitoring and Contribution Analytics](component_risk/) | Uses GitHub/Jira activity for contribution and risk views, with its own project accounts and login. | FastAPI `127.0.0.1:5000` | React/Vite `127.0.0.1:5175` | Local SQLite `ipms.db`; model artifacts |
| [Intelligent Team Formation and Topic Feasibility Analysis](component_team/component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/) | Generates Pareto team-allocation alternatives, checks technical requirement coverage, and supports capacity-aware supervisor assignment. | FastAPI `127.0.0.1:8003` | React/Vite `127.0.0.1:5174` | PostgreSQL `team_formation_db` |

The research website is maintained in a **separate repository** and is deliberately excluded from this code repository.

## Repository map

| Path | Purpose |
| --- | --- |
| `component_scheduling/` | Scheduler API, browser UI, separate test-only student submission portal, workload/progress/academic-scheduling services, and focused tests. |
| `component_quality/backend/`, `component_quality/frontend/`, `component_quality/training/` | Quality API, React UI, and model-training/evaluation pipeline. |
| `component_risk/ipms-risk-app/`, `component_risk/frontend/` | Risk API/login/database and React UI. |
| `component_team/component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/` | Active team-formation API and React UI. The nested path is the current layout. |
| `START_ALL.bat`, `START_ALL.ps1`, `svc*.bat` | Windows demo launchers for PostgreSQL and seven app processes. |
| `COMPONENT_DOCUMENTATION.md` | Additional component notes; component-level READMEs contain detailed setup and research context. |

## Local setup

Prerequisites: Python, Node.js/npm, and PostgreSQL for Scheduling, Quality, and Team Formation. The current Team Formation Vite build expects Node.js 20.19+ or 22.12+; older Node 20 releases may warn even if a build completes. Use separate Python virtual environments for the components because their ML dependencies differ. Risk uses its own SQLite database. Do not commit real `.env` files, credentials, uploads, or local databases.

1. Create PostgreSQL databases named `ipms_scheduling`, `researchpilot`, and `team_formation_db`. Create database users and permissions appropriate to your machine; do not reuse the placeholder passwords in example files.
2. Copy and fill the component environment examples:
   - `component_scheduling/.env.example` → `component_scheduling/.env`
   - `component_quality/backend/.env.example` → `component_quality/backend/.env`
   - `component_quality/frontend/.env.example` → `component_quality/frontend/.env` (if overriding the API URL)
   - `component_team/component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/backend-fastapi/.env.example` → `.env` in the same directory
3. In separate virtual environments, install `component_scheduling/requirements.txt`, `component_quality/backend/requirements.txt`, `component_risk/requirements.txt`, and the Team Formation backend `requirements.txt`. Install frontend packages with `npm ci` in the Quality, Risk, and Team Formation `frontend/` directories.
4. Run the Quality backend's Alembic migration from `component_quality/backend/` with `alembic upgrade head`. The Team Formation backend creates its tables at startup when `DATABASE_URL` is valid. Configure each component's local model artifacts or run its documented training/preparation steps where needed.

For the original Windows demo machine, `START_ALL.bat` starts PostgreSQL and all seven app services, then opens `http://127.0.0.1:8000/home`. **The batch launchers contain absolute local paths** (including the PostgreSQL executable); adjust them after cloning elsewhere, or use the manual commands below. Keep all service terminals open during the demo.

### Manual start commands

Run each block in a separate terminal after activating that component's Python environment. Paths are relative to the repository root.

```powershell
Set-Location component_scheduling
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location component_quality/backend
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 9000
```

```powershell
Set-Location component_quality/frontend
npm run dev
```

```powershell
Set-Location component_risk/ipms-risk-app
python -m uvicorn main:app --host 127.0.0.1 --port 5000
```

```powershell
Set-Location component_risk/frontend
npm run dev
```

```powershell
Set-Location component_team/component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/backend-fastapi
python -m uvicorn main:app --host 127.0.0.1 --port 8003
```

```powershell
Set-Location component_team/component_team/intelligent-team-formation-and-topic-feasiblity-analyzis/frontend
npm run dev
```

The optional standalone student document-submission test portal starts with `component_scheduling/run_student_submission_portal.bat` on `127.0.0.1:8010`, after the Scheduling API is running. It is a local testing interface, **not** institution-approved student authentication for production.

## How the components fit together

Team Formation produces team/project alternatives and confirmed allocations for staff review. Scheduling can display active Team Formation allocations and creates a separate proposal-based plan for a group. Its Gantt, workload, document-review, and signed GitHub-event workflows keep planned dates, activity evidence, and supervisor decisions distinct. Quality and Risk have their own APIs and interfaces. Portal navigation is integrated, but this repository does **not** claim that every cross-component API payload, group-ID mapping, or full end-to-end workflow has been verified. See [the Scheduling handoff pack](component_scheduling/Common_Report_Component_Handoff_Pack.md) for the documented integration boundaries and evidence.

## Safety, data, and reproducibility

- Never put actual `.env` files or webhook/API secrets in Git. GitHub webhooks require a shared secret configured in the Scheduling environment and repository settings. Do not expose the test portal or local services publicly without proper authentication and HTTPS.
- Raw proposals, dissertation drafts, training corpora, generated PDFs, uploads, local databases, virtual environments, and build outputs are excluded from the repository. Some model/data assets must be obtained or rebuilt separately; consult each component's README and environment example.
- A generated schedule is a planning suggestion, a GitHub event is activity evidence, and an approved document is a human review decision. None alone proves a student's work is complete.
- Use isolated test databases and synthetic fixtures for destructive/reset tests. Component-level tests and evaluation evidence are documented within their respective directories.

## Cleanup record

The [cleanup report](CLEANUP_REPORT_2026-10-13.md) lists obsolete local drafts and temporary render images moved out of this workspace. Training PDFs used by Quality, source research papers, submission fixtures, and linked Scheduling evidence screenshots were preserved.
