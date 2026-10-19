# IPMS Risk — Frontend

React + Vite frontend for the Predictive Risk Monitoring & Contribution Analytics component.
Uses the IPMS indigo/cyan visual style with a top navigation bar and card layout.

## Pages
- **Login / Signup** — cookie-session auth against the FastAPI backend
- **My Projects** — supervisors see the projects they supervise; students see their own team
- **Project Analytics** — click a project: live ML risk prediction, alerts, KPI tiles,
  Jira task status, 52-week commit chart, Contribution Index rankings, Jira task scores,
  and the registered team members. Auto-refreshes every 60 s. No manual inputs.

The top navigation opens the relevant section of Project Analytics. From My Projects,
choose a project first; the app does not provide separate React pages for these sections.

## Run
1. Start the backend (port 5000):
   `python -m uvicorn main:app --app-dir ../ipms-risk-app --port 5000`
2. `npm install` (first time)
3. `npm run dev` -> http://localhost:5175 (Vite proxies /api to port 5000)

Risk authentication is intentionally component-local. Scheduling, Quality, and Team
Formation credentials or tokens are not accepted by this component.
