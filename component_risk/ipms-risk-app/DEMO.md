# IPMS Demo Guide

**Intelligent Project Management System — Predictive Risk Monitoring & Contribution Analytics**

This guide walks through a full demo of the two implemented modules using live GitHub and Jira data.

---

## 1. Demo Assets

| Asset | Value |
|---|---|
| GitHub repository | `https://github.com/agronholm/exceptiongroup` |
| Jira project key | `IPMS` |
| Jira board | https://shehankrishan6.atlassian.net/browse/IPMS |

**Why this repo:** ~10 active contributors (team-sized, like a student project), with real commits, pull requests, issues, and code-review comments — so every Contribution Index component has live data.

**The Jira project** contains 12 tasks (titles mirror the repo's real issues) with a deliberately mixed profile:

| Status | Count | Detail |
|---|---|---|
| Done | 5 | 3 on time, 2 completed **late** |
| In Progress | 3 | 2 of them **overdue** |
| To Do | 4 | 1 overdue, 1 with no due date |

Expected metrics from this data:
- **Task completion rate:** 41.67%
- **Progress:** 54.17% (in-progress tasks count as half done)
- **Overdue tasks:** 3
- **Delay count:** 5 (2 completed late + 3 currently overdue)

---

## 2. Setup (once)

1. Check `ipms-risk-app/.env` exists with:

   ```env
   JIRA_BASE_URL = "https://shehankrishan6.atlassian.net"
   JIRA_EMAIL = "<your atlassian email>"
   JIRA_API_TOKEN = "<your api token>"
   GITHUB_TOKEN = "<optional but recommended for demo day>"
   ```

   > **Tip:** Without `GITHUB_TOKEN`, GitHub allows only 60 anonymous API requests/hour.
   > One contribution analysis uses ~10–20 requests. Create a token at
   > https://github.com/settings/tokens (no scopes needed for public repos) to get 5,000/hour.

2. Install dependencies (once):

   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Start the server:

   ```powershell
   .venv\Scripts\python.exe -m uvicorn main:app --app-dir ipms-risk-app --port 5000
   ```

4. Open http://localhost:5175

---

## 3. Demo Flow

### Part 0 — Sign in and roles (FR1)

The app now requires a login and has two roles: **Student** and **Supervisor**.

1. Open http://localhost:5175 — the Risk component sign-in page appears.
2. Click **Create one** and register a **Supervisor** account (e.g. `sup@uni.lk` / `password123`).
3. You land on **My Projects**. Create a project:
   - Project Name: `ExceptionGroup Port`
   - Team ID: `TEAM-IPMS`
   - GitHub URL: `https://github.com/agronholm/exceptiongroup`
   - Jira Project Key: `IPMS`
4. In a second browser (or a private window), register a **Student** account.
   They see *"You have not been added to a project team yet."*
5. Back as the supervisor, open the project and **Add a Student** — or, for many teams at
   once, use **Bulk Upload Teams (Excel)** on My Projects: download the template, fill one
   row per member (Project ID, Name, Team Leader, Member Name, IT Number, IT Email,
   GitHub Username, Repo URL, Jira key), and upload. Student accounts are created
   automatically with the **IT number as the first password** — optionally typing their
   GitHub username and Jira display name so the analytics can match them to their activity.
6. Refresh the student's page: the project now appears with Dashboard / Contributions / Risk links.

**What to point out:**

| | Student | Supervisor |
|---|---|---|
| See own project | ✅ | ✅ |
| See other teams | ❌ blocked | ❌ (only own projects) |
| Create / edit projects | ❌ | ✅ |
| Add / remove members | ❌ | ✅ |
| Analyse any repo by URL | ❌ | ✅ |

- Passwords are stored as **salted PBKDF2-SHA256** hashes (200,000 rounds) — never in plain text.
- Access is enforced **server-side on every page and API endpoint**, not just hidden in the UI.
  Try opening `/projects/1` as an unassigned student — it redirects with an access-denied message.
- Sessions are HTTP-only cookies that expire after 7 days; **Sign out** invalidates them immediately.

### Part A — Contribution Index (per-member analytics)

1. Click **Contribution Index** in the top navigation.
2. Enter:
   - GitHub Repository URL: `https://github.com/agronholm/exceptiongroup`
   - Jira Project Key: `IPMS`
3. Click **Calculate Contribution Index** (takes ~10–20 s — live API calls).

**What to point out:**

- **Team summary cards** — average CI, total commits, merged PRs, issues resolved, comments.
- **Ranked member cards** — each member has a CI score (0–100) built from five weighted components:

  | Component | Weight | Source |
  |---|---|---|
  | Commit Activity | 30% | commits vs. team's top committer |
  | Task Completion | 25% | merged pull requests |
  | Collaboration | 20% | comments + issues opened |
  | Issue Resolution | 15% | issues closed (credited to assignees) |
  | Code Quality | 10% | PR acceptance rate (merged / opened) |

- Expected top result: **agronholm** with CI ≈ 84 and ~24% contribution share, followed by a realistic tail — shows the index separates a lead contributor from occasional ones.
- Bots (dependabot, coveralls, etc.) are filtered out automatically.
- Scroll to the bottom: **Task Contribution (Jira — IPMS)** — project task summary plus per-assignee task scores and on-time completion rates from the live Jira board.

### Part B — Risk Prediction (ML + live data)

1. Click **Risk Prediction** in the navigation.
2. Fill in:
   - Project Name: `ExceptionGroup Port` (anything)
   - Team ID: `TEAM-IPMS`
   - GitHub Repository URL: `https://github.com/agronholm/exceptiongroup`
   - Jira Project Key: `IPMS`
3. Click **Fetch from Jira** — *the wow moment*: the four Delivery fields
   (Overdue Tasks, Delay Count, Task Completion Rate, Progress %) fill in live from the Jira board.
4. Enter Team Quality values (e.g. from Part A: Code Quality `70`, Collaboration `65`, Overall CI `60` — team average).
5. Click **Predict Risk**.

**Expected result: High Risk** — the repo has ~147 inactive days and 0 commits this week, and the Jira board shows 5 delays. The result panel confirms *"Delivery metrics fetched live from Jira project IPMS"* and lists all 12 features fed to the ML model (Logistic Regression, 97.6% test accuracy).

### Part C — Real-Time Analytics Dashboard (FR9)

1. Click **Dashboard** in the navigation.
2. Enter the repo URL + Jira key `IPMS`, click **Load Dashboard** (or bookmark the URL —
   the project is encoded in the query string).

**What to point out:**

- **Everything is derived automatically** — no manual inputs at all. The dashboard fetches
  GitHub + Jira live, computes the team's CI/collaboration/quality scores itself, and runs
  the ML risk prediction on the derived features.
- **Risk alerts panel (FR12)** — colour-coded alerts: predicted risk level, inactivity,
  overdue tasks, late completions, high-priority bugs, uneven participation.
- **KPI tiles** — risk status, progress, completion rate, overdue, delays, weekly commits,
  inactive days, team average CI.
- **Charts** — Jira task status breakdown (stacked bar), commits per week for the last
  52 weeks (hover any bar for the exact week), top contributors by CI, and Jira task
  scores per assignee.
- **Real-time behaviour** — auto-refreshes every 60 s ("Updated HH:MM:SS (live/cached)"
  in the toolbar); the server caches results for 2 minutes to protect API rate limits;
  **Refresh Now** forces a live re-fetch.
- Combine with Part D: change something in Jira, hit Refresh Now, and the KPIs, task
  chart, and alerts all update on one screen.

### Part D — Live update (optional, strongest closer)

1. Open the Jira board and move one **To Do** task to **Done**.
2. Back in the app, click **Fetch from Jira** again → completion rate rises instantly.
3. Re-predict → show that the risk inputs track the real project state in real time.

### Part E — Automatic risk emails (FR12)

1. In `.env`, fill in the SMTP settings (Gmail: create an **App Password** under
   Google Account → Security → 2-Step Verification → App passwords):

   ```env
   SMTP_HOST = "smtp.gmail.com"
   SMTP_PORT = "587"
   SMTP_USERNAME = "yourgmail@gmail.com"
   SMTP_PASSWORD = "your-16-char-app-password"
   ```

2. Restart the server. Sign in as a supervisor and verify the setup:

   ```bash
   curl -X POST http://localhost:5000/api/test-email -b "ipms_session=<your cookie>"
   ```

   (Or simply run it from the browser console on any page:
   `fetch('/api/test-email', {method:'POST'}).then(r=>r.json()).then(console.log)`)

3. Open the dashboard for a registered project that predicts **High Risk** —
   within seconds every team member and the supervisor receive an email with the
   key metrics, the active alerts, and a link to the live dashboard.

**What to point out:**
- The email fires from three paths: a **background monitor** (default: every 60 min,
  even with nobody watching), fresh dashboard loads, and manual predictions.
- Anti-spam: max one email per project per hour, and a 24 h cooldown while the
  project *stays* at risk. Every alert is logged in the `risk_alerts` table.
- If SMTP is not configured the feature simply stays off (the dashboard shows a hint).

You can also demo the sample presets (High/Medium/Low buttons) if the network is down — they bypass all API calls.

---

## 4. What Is Implemented (talking points)

- **FR1** — secure registration and login with **Student** and **Supervisor** roles; server-side
  role-based access control (29 automated access-control tests passing).
- **FR5** — automated data collection from GitHub (VCS) *and* Jira (ITS) via secure API integration.
- **FR7** — per-member Contribution Index: weighted, multi-source, relative-to-team scoring with renormalization when a team doesn't use a feature (e.g. no PRs).
- **FR8** — ML risk prediction (Logistic Regression / Gradient Boosting / Random Forest / Decision Tree trained; best model served).
- **FR9** — real-time analytics dashboard: auto-derived KPIs, task/commit/contribution charts, 60 s auto-refresh with server-side caching.
- **FR12** — automatic risk emails to the team and supervisor when a project becomes High Risk, driven by a background monitor with anti-spam cooldowns.
- **FR12 (partial)** — automated risk alerts panel (risk level, inactivity, overdue tasks, late completions, uneven participation).
- Security: credentials in `.env` (never committed), token-authenticated API calls.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| "GitHub API rate limit reached" warning | Add `GITHUB_TOKEN` to `.env`, restart server |
| "Jira is not configured" | Check `.env` values; restart the server after edits |
| "Jira project not found" | Confirm key `IPMS` exists and the API token's account can see it |
| Analysis feels slow | Normal — live pagination over the GitHub API; use a smaller repo |
| All Jira scores are 0 | Tasks need assignees, due dates, and some Done/In-Progress statuses |
| Redirected to /login | Expected — sign in first; every page requires an account |
| Student sees "no projects" | Their supervisor must add them to a project team |
| Forgot a password | No reset flow yet; register a new account or delete `ipms.db` to start over |

## 6. Regenerating the Demo Data

The Jira demo project was generated by `scripts/jira_demo_setup.py`, which reads `.env`,
creates project `IPMS`, creates 12 tasks (real issue titles from the demo repo, mixed due
dates/assignees), and transitions them to Done / In Progress. To rebuild the data, delete
the project in Jira (Settings → Projects → Trash), then run:

```powershell
.venv\Scripts\python.exe ipms-risk-app\scripts\jira_demo_setup.py
```
