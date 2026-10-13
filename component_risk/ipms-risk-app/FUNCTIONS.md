# IPMS — Function Guide (Plain English)

This document explains **every function** in the application in simple terms, so anyone —
even without deep programming knowledge — can understand what each part does.

The application has eight Python code files:

| File | Job |
|---|---|
| `main.py` | The web server: pages, buttons, GitHub metrics, the ML risk prediction, and the dashboard |
| `contribution.py` | Talks to GitHub and calculates each team member's **Contribution Index** |
| `jira_client.py` | Talks to Jira and calculates **task/delivery metrics** |
| `database.py` | Stores users, projects, team members and login sessions in SQLite |
| `auth.py` | Passwords, login sessions, and the Student/Supervisor access rules |
| `emailer.py` | Sends emails through SMTP (configured in `.env`) |
| `risk_monitor.py` | Automatic risk emails: notifies the team when a project becomes high risk |
| `bulk_upload.py` | Excel uploader: a supervisor creates whole teams (projects + student accounts) from one .xlsx file |

Supporting files: `best_risk_prediction_model.pkl` (the trained ML model), `scaler.pkl`
(scales numbers before the model reads them), `templates/` (the HTML pages), `static/`
(the styling), and `.env` (secret keys — never shared).

---

## Part 1 — `main.py` (the web server)

### Setup (top of the file)
Before any page loads, the app:
1. Reads secret keys (Jira login, GitHub token) from the `.env` file.
2. Loads the trained ML model and the scaler from disk.
3. Defines `FEATURE_COLUMNS` — the **12 pieces of information** the model needs to judge risk.
4. Defines `LABEL_MAP` — translates the model's answer (0, 1, 2) into words (High / Low / Medium Risk).
5. Defines `SAMPLE_GITHUB_METRICS` — fake demo numbers for the High/Medium/Low sample buttons, so you can demo without the internet.

### GitHub helper functions

| Function | In plain English |
|---|---|
| `extract_github_owner_repo(url)` | Takes a link like `github.com/pallets/flask` and pulls out the owner (`pallets`) and repo name (`flask`). Returns nothing if the link is invalid. |
| `get_paginated_count(url, ...)` | Counts how many items exist (e.g. total commits) without downloading them all. It asks GitHub for "1 per page" and reads the last page number — a fast way to count thousands of items. |
| `get_latest_commit_date(url, ...)` | Finds the date of the most recent commit, used to work out how long the project has been inactive. |
| `get_all_paginated_items(url, ...)` | Downloads a full list from GitHub (e.g. every issue), 100 at a time, following the "next page" links until there are none left. |
| `get_github_metrics(url)` | **The main GitHub gatherer.** Uses the helpers above to produce 5 numbers: total commits, commits this week, inactive days, bug count, and high-priority bug count. Skips pull requests when counting bugs. If the link is bad, returns all zeros. |
| `get_weekly_commit_activity(url)` | Gets a "commits per week for the last 52 weeks" list from GitHub, used to draw the commit chart on the dashboard. |
| `get_github_rate_remaining()` | Asks GitHub "how many more requests am I allowed this hour?" Used to warn the user before they run out. |

### The web pages (routes)

A "route" is a web address the browser can visit. Each function below runs when someone
opens that address.

| Route (address) | Function | What it does |
|---|---|---|
| `GET /` | `home()` | Shows the **Risk Prediction** page with default demo values filled in. |
| `POST /predict` | `predict_risk(...)` | Runs when you click **Predict Risk** — explained in detail below. |
| `GET /contribution` | `contribution_page()` | Shows the empty **Contribution Index** page. |
| `POST /contribution` | `analyze_contribution(...)` | Runs when you submit a repo (and optional Jira key) — calculates and shows every member's Contribution Index plus Jira task contribution. |
| `GET /dashboard` | `dashboard_page(...)` | Shows the **Dashboard** shell. The actual data loads afterwards via JavaScript. |
| `GET /api/dashboard-data` | `dashboard_data(...)` | The dashboard's data feed (returns JSON, not a page). Uses a **2-minute cache** so repeated refreshes don't overload the APIs. |
| `GET /api/jira-metrics` | `jira_metrics(...)` | A small helper the "Fetch from Jira" button calls to grab task numbers on demand. |

### `predict_risk(...)` — step by step

This is the heart of the Risk Prediction page. When you click **Predict Risk**:

1. **Gather GitHub numbers** — if a sample button is active it uses the fake demo numbers;
   otherwise it fetches the real repo with `get_github_metrics`.
2. **Check Jira** — if you entered a Jira project key, it fetches live task data and
   **replaces** the four delivery fields you typed (overdue, delays, completion, progress)
   with the real Jira values. If Jira fails, it keeps your typed values and shows a warning.
3. **Assemble the 12 features** into one row of data.
4. **Scale and predict** — the scaler adjusts the numbers to the range the model expects,
   then the model outputs 0, 1, or 2, which becomes "High/Low/Medium Risk".
5. **Show the result** — the page displays the risk badge and every number that fed the model.

### Dashboard engine functions

| Function | In plain English |
|---|---|
| `build_dashboard_data(github_url, jira_key)` | **The dashboard's brain.** Gathers everything at once — Contribution Index, GitHub metrics, weekly commits, and Jira data — then *derives* the three Team Quality scores (see METRICS.md), runs the risk prediction automatically (no manual typing), and packages it all up with alerts and warnings. |
| `build_dashboard_alerts(...)` | Looks at the results and writes plain-English warnings: predicted risk level, "no commits in N days", overdue tasks, late completions, open high-priority bugs, and uneven participation (one person doing more than 60% of the work). If nothing is wrong, it says the project looks healthy. |
| `dashboard_data(...)` | The caching layer. If fresh data (under 2 minutes old) exists it returns that instantly; otherwise it rebuilds. The "Refresh Now" button forces a rebuild. |

---

## Part 2 — `contribution.py` (Contribution Index engine)

This file answers: *"How much did each team member contribute, fairly?"*

| Function | In plain English |
|---|---|
| `build_headers()` | Prepares the GitHub request, adding your secret token if you have one (so you get 5,000 requests/hour instead of 60). |
| `extract_owner_repo(url)` | Same as in main.py — splits a GitHub link into owner and repo. |
| `fetch_all_pages(url, ...)` | Downloads a complete GitHub list 100 items at a time. Unlike the main.py version, it also records **warnings** (rate limit hit, network error, etc.) to show the user. |
| `is_bot(login)` | Decides whether an account is a robot (like `dependabot` or `coveralls`) so bots don't get scored as team members. |
| `new_member_stats()` | Creates a blank scorecard for a member (0 commits, 0 PRs, etc.). |
| `collect_member_stats(owner, repo)` | **The data gatherer.** Visits five GitHub sources — contributors, pull requests, issues, issue comments, review comments — and tallies each person's commits, PRs opened/merged, issues opened/resolved, and comments. Robots are ignored; pull requests are not mistaken for issues. |
| `relative_score(value, max)` | Turns a raw number into a 0–100 score compared to the team's best. Example: if the top committer made 100 commits and you made 40, you score 40. |
| `component_raw_values(member)` | Pulls out the four raw numbers that get compared across the team (commits, merged PRs, issues resolved, collaboration). |
| `compute_contribution_index(url)` | **The main calculator.** For every member it scores the five components (Commit Activity, Task Completion, Collaboration, Issue Resolution, Code Quality), combines them using the weights, and produces one Contribution Index (0–100). It also: ranks members, calculates each person's **share** of the team's total, computes team averages, and handles the case where a team never used a feature (drops that component and rebalances the weights). Exact formulas are in `METRICS.md`. |

**The five components and their weights:**
Commit Activity (30%), Task Completion (25%), Collaboration (20%), Issue Resolution (15%),
Code Quality (10%).

---

## Part 3 — `jira_client.py` (Jira / task tracking engine)

This file answers: *"How is the project delivery going, and who is doing the tasks?"*

| Function | In plain English |
|---|---|
| `get_config()` | Reads the three Jira secrets (site address, email, token) from the environment. |
| `is_configured()` | Returns yes/no on whether all three secrets are present. |
| `is_valid_project_key(key)` | Checks the project key looks sensible (letters/numbers) before using it — a safety check against bad input. |
| `parse_due_date(value)` | Converts Jira's due-date text into a real date the computer can compare. Returns nothing if empty or malformed. |
| `parse_datetime(value)` | Same idea, but for the full completion timestamp (with time and timezone). |
| `fetch_project_issues(key)` | **The Jira downloader.** Logs in and pulls every task in the project, 100 at a time. Gives clear error messages for wrong password (401), missing project (400), or network trouble. |
| `classify_issue(fields, today)` | Looks at one task and decides three things: its status (Done / In Progress / To Do), whether it is **overdue** (not done and past its due date), and whether it was **completed late** (finished after its due date). |
| `compute_project_metrics(issues)` | **The delivery calculator.** Counts all tasks by status and produces the project-level numbers: total, done, in-progress, to-do, overdue, delays, completion rate, and progress %. (In-progress tasks count as half-done for progress.) |
| `compute_member_task_stats(issues)` | **The per-person calculator.** For each assignee, counts assigned/completed/in-progress/overdue/late tasks, then gives a Task Score (relative to the team's top finisher) and an on-time completion rate. |
| `get_jira_analytics(key)` | The all-in-one wrapper: downloads the issues, then returns both the project metrics and the per-member stats together — or a clean error if something went wrong. |


---

## Part 4 — `database.py` (storage)

All data lives in a single SQLite file, `ipms.db`, created automatically on first run.

| Table | What it holds |
|---|---|
| `users` | One row per person: email, full name, password hash, salt, role (`student` or `supervisor`) |
| `projects` | One row per team project: name, team ID, GitHub URL, Jira key, and which supervisor owns it |
| `project_members` | Which students belong to which project, plus their GitHub username and Jira display name |
| `sessions` | Active logins: a random token, the user it belongs to, and when it expires |

| Function | In plain English |
|---|---|
| `connect()` | Opens the database file, with foreign keys switched on. |
| `init_db()` | Creates the four tables if they do not exist yet (safe to call every start-up). |
| `create_user` / `get_user_by_email` / `get_user_by_id` / `list_students` | Add and look up people. |
| `create_session` / `get_session_user` / `delete_session` | Remember who is logged in. Expired tokens are deleted automatically when used. |
| `create_project` / `get_project` / `update_project` | Add and edit team projects. |
| `list_projects_for_supervisor(id)` | Only the projects that supervisor owns. |
| `list_projects_for_student(id)` | Only the projects that student is a member of. |
| `add_member` / `remove_member` / `list_members` / `is_member` | Manage who is on a team. |

---

## Part 5 — `auth.py` (login and permissions)

| Function | In plain English |
|---|---|
| `hash_password(password)` | Scrambles a password using PBKDF2-SHA256 with 200,000 rounds and a random salt. Passwords are **never** stored in readable form. |
| `verify_password(...)` | Re-scrambles the typed password and compares it safely (constant-time, so attackers cannot guess by measuring response times). |
| `validate_registration(...)` | Checks the sign-up form: name present, email looks real, password at least 8 characters, valid role, email not already used. |
| `register_user(...)` | Creates the account with a hashed password. |
| `login(email, password)` | Checks the credentials and, on success, issues a random session token. On failure it returns the *same* message whether the email or the password was wrong, so nobody can discover which emails exist. |
| `logout(token)` | Deletes the session so the cookie stops working. |
| `current_user(request)` | Looks at the browser's session cookie and returns the logged-in user (or nothing). |
| `set_session_cookie` / `clear_session_cookie` | Sets an HTTP-only cookie (JavaScript cannot read it) that lasts 7 days. |
| **`can_access_project(user, project)`** | **The core rule.** A supervisor may see a project only if they own it. A student may see it only if they are a member of it. |
| `visible_projects(user)` | The list of projects this person is allowed to see. |
| `resolve_project(user, project_id)` | Loads a project **only** if the person is allowed to see it — otherwise returns nothing. Every analysis page uses this. |

### The two roles

| | **Student** | **Supervisor** |
|---|---|---|
| Sign up / sign in | ✅ | ✅ |
| See own project(s) | ✅ (only projects they are a member of) | ✅ (only projects they supervise) |
| See other teams' data | ❌ blocked | ❌ blocked (not their projects) |
| Create a project | ❌ | ✅ |
| Edit project details | ❌ | ✅ |
| Add / remove team members | ❌ | ✅ |
| Run Risk / Contribution / Dashboard | ✅ for their own project | ✅ for their projects |
| Analyse any repository by typing a URL | ❌ | ✅ |

In `main.py`, `resolve_analysis_target()` enforces the last two rows: a student's
repo and Jira key always come from their assigned project, while a supervisor may
also type in an arbitrary repository.


---

## Part 6 — `emailer.py` and `risk_monitor.py` (automatic risk emails)

When a registered project's predicted risk becomes **High Risk**, the system
automatically emails **every team member and the supervisor**.

### `emailer.py`

| Function | In plain English |
|---|---|
| `get_config()` | Reads the SMTP settings (server, port, username, password, sender) from `.env`. |
| `is_configured()` | Yes/no: has an email server been set up? If not, the whole feature quietly stays off. |
| `send_email(recipients, subject, body)` | Connects to the mail server, logs in, and sends a plain-text email. Returns a readable error message if anything fails — it never crashes the app. |

### `risk_monitor.py`

| Function | In plain English |
|---|---|
| `build_alert_email(...)` | Writes the email: project name, predicted risk, the key numbers (progress, overdue tasks, delays, inactive days, team CI), the active alerts, and a link to the live dashboard. |
| `evaluate_project_risk(project, risk_status, data)` | **The decision maker.** Records the latest risk status, then decides whether to email: only for High Risk, only if email is configured, and never more than once an hour per project. While a project *stays* at risk, it waits out a cooldown (default 24 h) before reminding again. |

### When do the emails actually fire?

1. **Background monitor** — a thread checks every registered project on an interval
   (default every 60 minutes), even if nobody has the app open.
2. **Dashboard loads** — every fresh (non-cached) dashboard build for a registered project.
3. **Manual predictions** — every Predict Risk run on a registered project.

All three paths go through the same cooldown logic, so overlapping triggers never
cause duplicate emails. Every sent alert is recorded in the `risk_alerts` table.

### Setup (in `.env`)

```env
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USERNAME = "yourgmail@gmail.com"
SMTP_PASSWORD = "your-16-char-app-password"   # Google Account -> Security -> App passwords
APP_BASE_URL = "http://127.0.0.1:5175"        # React project view used in alert emails
```

Restart the server after editing. A supervisor can verify the setup by calling
`POST /api/test-email`, which emails themselves a test message.


---

## Part 7 — `bulk_upload.py` (Excel team uploader)

A supervisor can create many teams at once by uploading one Excel file
(**one row per member**). Download the ready-made template from the
My Projects page ("Download Template").

| Column | Required? | What it becomes |
|---|---|---|
| Project ID | yes | The team identifier (e.g. TEAM-101); re-uploading the same ID updates instead of duplicating |
| Project Name | yes | The project's display name |
| Team Leader | one "Yes" per team | Marks that member as leader (badge in the team list) |
| Member Name | yes | The student's full name |
| IT Number | for new accounts | Stored on the account **and used as the first password** |
| IT Email | yes | The login email — also where risk alert emails go |
| GitHub Username | recommended | Links the student to their commits/PRs in the Contribution Index |
| GitHub Repo URL | recommended | The project repository the analytics and risk model read |
| Jira Project Key | optional | Connects the Jira board |

| Function | In plain English |
|---|---|
| `build_template()` | Generates the downloadable .xlsx template, with example rows. |
| `parse_workbook(bytes)` | Reads the upload: finds the header row (column names are matched loosely, so "IT Mail" or "it_email" both work), groups rows by Project ID, and collects row-level errors (missing email, missing IT number, ...) without failing the whole file. |
| `apply_upload(groups, supervisor_id)` | Creates or updates each project, creates missing student accounts (password = IT number), links members with their GitHub usernames and leader flag, and reports exactly what happened per project. |
| `process_upload(...)` | The full pipeline; returns the summary shown on screen (created/updated/members/accounts + every problem found). |

Safety rules: only supervisors can upload; a Project ID owned by another supervisor is
skipped; existing accounts never have their passwords changed; broken rows are reported
individually while the rest of the file still imports.

---

## How the pieces work together (the big picture)

```
                    ┌─────────────────┐
   GitHub API ─────▶│ contribution.py │──▶ per-member Contribution Index
                    └─────────────────┘
                    ┌─────────────────┐
   GitHub API ─────▶│  main.py        │──▶ repo metrics (commits, bugs)
                    │  (get_github_*) │
                    └─────────────────┘
                    ┌─────────────────┐
   Jira API ───────▶│  jira_client.py │──▶ delivery metrics + per-assignee tasks
                    └─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ ML model        │──▶ Risk Status (High/Medium/Low)
                    │ (.pkl files)    │
                    └─────────────────┘
                             │
                             ▼
              Risk Prediction page · Contribution page · Dashboard
```

- **Sign in** — everyone must log in; the session cookie identifies them on every page.
- **My Projects** — the landing page, filtered by role (supervisors see projects they own,
  students see the project they belong to).
- **Risk Prediction page** — you provide inputs (some auto-fetched); the model predicts risk.
- **Contribution Index page** — shows fair per-member scores from GitHub, plus Jira tasks.
- **Dashboard** — combines *everything* automatically, refreshes live, and raises alerts.

For the exact formula behind every number, see **`METRICS.md`**.
For how to run a demo, see **`DEMO.md`**.
