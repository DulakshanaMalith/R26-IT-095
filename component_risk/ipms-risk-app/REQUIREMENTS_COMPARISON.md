# IPMS — Requirements vs. Current Work

This document compares the **proposal** (IT22109576 Project Proposal Report) against what
is **actually built** so far, so you can see progress at a glance and know what remains.

## Scope note

The proposal describes a full system with **four modules**:

1. Intelligent Team Formation & Topic Feasibility
2. Generative Project Planning & Adaptive Scheduling
3. **Predictive Risk Monitoring & Contribution Analytics** ← *your individual research component*
4. Automated Quality Assessment & Adaptive Mentorship

The current application implements **Module 3**. Requirements that clearly belong to the other
three modules or to shared platform infrastructure are marked accordingly — they are not
your individual deliverable, but they are listed for completeness.

Legend: ✅ Done · 🟡 Partial · ⬜ Not started · ➖ Other module / out of your scope

---

## 1. Specific Objectives (Section 2.2)

| # | Objective (from proposal) | Status | Evidence / Notes |
|---|---|---|---|
| O1 | Develop a **Contribution Index** (quantitative + qualitative, task complexity & collaboration) | ✅ | `contribution.py` — 5 weighted components from live GitHub data, per member, with fair relative scoring. Quantitative done; "task complexity" weighting is basic (see gaps). |
| O2 | **ML models for predictive risk** (delays, bottlenecks, failure) | ✅ | 4 models trained (LR 97.6%, GB, RF, DT); best model served in the app; predicts High/Medium/Low. |
| O3 | **Real-time analytics dashboards** (progress, contributions, risk, KPIs) | ✅ | `/dashboard` — auto-refreshing KPIs, charts, contributor rankings, live risk status. |
| O4 | **Validate IPMS performance** (prediction accuracy, CI fairness, usability) | 🟡 | Model accuracy measured (confusion matrices, classification reports). CI fairness study vs. supervisor/peer scores, ROC-AUC, and SUS usability testing are **not yet done**. |
| O5 | Align with **academic assessment standards** (grading fairness, learning outcomes) | ⬜ | Not yet — needs the CI fairness validation and supervisor input loop. |
| O6 | Enhance collaborative learning via **actionable recommendations/feedback** | 🟡 | Dashboard alerts flag problems (inactivity, uneven participation); tailored recommendations/feedback are basic. |
| O7 | **Continuous improvement** by incorporating supervisor/student feedback | ⬜ | No feedback capture or model-retraining loop yet. |

---

## 2. Functional Requirements (Section 5.2, Table 3)

| ID | Requirement | Status | What exists / what's missing |
|---|---|---|---|
| FR1 | Secure register & login for users | ✅ | `auth.py` + `/register`, `/login`, `/logout`. PBKDF2-SHA256 password hashing (200k rounds, random salt), HTTP-only session cookies with 7-day expiry. |
| FR2 | Admin manages accounts & permissions | 🟡 | **Supervisor** role manages its own projects and team membership (add/remove students, link GitHub/Jira identities). A separate system-administrator role is not built. |
| FR3 | Students create project profiles & form teams | 🟡 | Intelligent team formation belongs to Module 1, but supervisors can now bulk-create teams (projects + member accounts + leader) from one Excel file. |
| FR4 | Teams submit & manage project topics | ➖ | Belongs to Module 1. |
| FR5 | **Collect activity data from GitHub & PM tools via API** | ✅ | GitHub REST API (`get_github_metrics`, `contribution.py`) **and** Jira Cloud API (`jira_client.py`) both integrated live. |
| FR6 | **Process and store** activity data (commits, issues, tasks) | 🟡 | Processing ✅. Storing 🟡 — SQLite (`database.py`) now persists **users, projects, team membership and sessions**; collected GitHub/Jira activity and prediction history are still re-fetched per request (2-min cache). |
| FR7 | **Calculate individual contribution metrics** | ✅ | Contribution Index per member (GitHub) + per-assignee task stats (Jira). |
| FR8 | **Apply ML to predict project risks** | ✅ | Trained model integrated; prediction on both the Risk page and the Dashboard. |
| FR9 | **Generate visual dashboards** (progress, contributions, risk) | ✅ | Full dashboard with KPIs, task-status chart, commit chart, contributor rankings. |
| FR10 | Supervisors review progress & give feedback | ⬜ | No supervisor feedback capture (needs auth + database first). |
| FR11 | Generate reports summarizing performance & contributions | 🟡 | Data is all computed and on-screen; there is no exportable report (PDF/print) yet. `METRICS.md` documents the numbers. |
| FR12 | **Notifications/alerts when risks are detected** | ✅ | On-screen alert panel **plus automatic risk emails**: a background monitor re-checks every registered project on an interval and emails the team + supervisor when a project becomes High Risk (with anti-spam cooldowns). |

**Your module's core FRs (FR5, FR7, FR8, FR9) are complete**, plus FR1 (authentication with
Student/Supervisor roles). FR2, FR6, FR11 and FR12 are partial. FR10 is now unblocked —
accounts, roles and storage exist, so supervisor feedback can be built next.

---

## 3. Technical Methods (Section 3.2) — did we build what we said?

| Proposed method | Status | Notes |
|---|---|---|
| Contribution Index (weighted: commits, code quality, tasks, issues, collaboration) | ✅ | All five factors implemented as weighted components. |
| Risk models: **Random Forest, Gradient Boosting, Logistic Regression** | ✅ | All three trained (plus Decision Tree). |
| Cross-validation & hyperparameter tuning | 🟡 | Basic train/test split and accuracy done; systematic CV + tuning should be strengthened for the final report. |
| Data preprocessing (clean, normalize, feature extraction) | ✅ | Scaler + structured 12-feature extraction from live sources. |
| Temporal features (activity bursts, recency) | 🟡 | `weekly_commits`, `inactive_days` capture some recency; richer temporal features (per-week bursts per member) are a future improvement. |
| Visualization & real-time dashboards | ✅ | Implemented. |

---

## 4. Tools & Platforms (Section 3.3) — planned vs. used

| Planned tool | Used? | Notes |
|---|---|---|
| Python | ✅ | Core language. |
| Scikit-learn | ✅ | Model training and prediction. |
| GitHub API | ✅ | Fully integrated. |
| Jira API | ✅ | Fully integrated. |
| Database (MongoDB / PostgreSQL) | 🟡 | **SQLite** used instead (`ipms.db`) — zero-setup and ideal for this stage; the schema ports directly to PostgreSQL later. Currently stores accounts/projects/teams, not yet activity history. |
| Web dashboards (React / web-based) | 🟡 | Built with **FastAPI + HTML/CSS/JS** instead of React — functionally equivalent for this stage; React is optional. |

---

## 5. Non-Functional Requirements (Section 5.3)

| Requirement | Status | Notes |
|---|---|---|
| Security | ✅ | Secrets in `.env` (git-ignored); token-authenticated API calls; salted PBKDF2 password hashing; HTTP-only session cookies; role-based access control enforced server-side on every page and API endpoint. |
| Performance | ✅ | Fast pagination counting; 2-minute dashboard cache to limit API load. |
| Usability | ✅ | Clean, consistent UI across all pages; role-aware navigation; sample presets for offline demo. |
| Scalability | 🟡 | Handles many projects and users via the SQLite layer; a move to PostgreSQL and a shared cache would be needed for large multi-institution deployment. |
| Reliability | ✅ | Graceful error handling everywhere (bad URL, rate limits, Jira errors) — app never crashes on bad input. |
| Maintainability | ✅ | Modular files (main / contribution / jira_client / database / auth), documented in `FUNCTIONS.md` and `METRICS.md`. |
| Compatibility | ✅ | Works with GitHub and Jira; runs on any OS/browser. |
| Extensibility | ✅ | New metrics/weights are easy to add (weights in one dict; clear module boundaries). |

---

## 6. Summary — where the project stands

### ✅ Done (your module's core)
- **Authentication with Student & Supervisor roles** (FR1, part of FR2) — 29 access-control tests passing
- Live **GitHub** data collection (FR5)
- Live **Jira** data collection (FR5)
- **Contribution Index** per member (FR7, O1)
- **ML risk prediction** (FR8, O2)
- **Real-time dashboard** with charts, KPIs, alerts (FR9, O3, partial FR12)
- Robust error handling, clean UI, full documentation

### 🟡 Partial — good next steps
- **FR6 — Database**: persist collected data, metrics, and prediction history *(highest priority; unlocks FR10/FR11)*
- **FR11 — Reports**: exportable PDF/printable summary
- **O4 — Validation**: ROC-AUC, cross-validation, CI-fairness study vs. supervisor scores, SUS usability testing (needed for the final report)

### ⬜ Not started (mostly platform-wide or other modules)
- **FR10** — Supervisor feedback capture
- **O5/O7** — Assessment-standard alignment & feedback-driven retraining loop
- **FR3/FR4** — Team formation & topic management (Module 1, not your component)

### Recommended order to tackle next
1. **Persist activity & prediction history** (rest of FR6) — store each analysis run so trends
   over time can be charted, using the SQLite layer that already exists.
2. **Supervisor feedback + reports** (FR10/FR11) — now unblocked by accounts and roles.
3. **Validation study** (O4) — ROC-AUC, cross-validation, CI-fairness vs. supervisor scores,
   SUS usability testing — needed for the final thesis.
