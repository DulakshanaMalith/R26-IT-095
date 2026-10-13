# IPMS Risk — Frontend

React + Vite frontend for the Predictive Risk Monitoring & Contribution Analytics component.
Same design language as component_quality's frontend (indigo/cyan, dark sidebar, card layout).

## Pages
- **Login / Signup** — cookie-session auth against the FastAPI backend
- **My Projects** — supervisors see the projects they supervise; students see their own team
- **Project Analytics** — click a project: live ML risk prediction, alerts, KPI tiles,
  Jira task status, 52-week commit chart, Contribution Index rankings, Jira task scores,
  and the registered team members. Auto-refreshes every 60 s. No manual inputs.

## Run
1. Start the backend (port 5000):
   `python -m uvicorn main:app --app-dir ../ipms-risk-app --port 5000`
2. `npm install` (first time)
3. `npm run dev` -> http://localhost:5175 (Vite proxies /api to port 5000)

Risk authentication is intentionally component-local. Scheduling, Quality, and Team
Formation credentials or tokens are not accepted by this component.
