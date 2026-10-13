# IPMS Metrics Reference

**How every field in the system gets its value.**

The ML risk model takes 12 features. Depending on the page, each feature is either
typed manually, fetched live from GitHub or Jira, or derived from other computed metrics.

| Source legend | Meaning |
|---|---|
| 🖊 Manual | typed by the user in the form |
| 🐙 GitHub | fetched live from the GitHub REST API |
| 🟦 Jira | fetched live from the Jira Cloud REST API |
| ⚙ Derived | computed from other live metrics |

---

## 1. Risk Prediction page — the 12 model features

### Project Activity (from GitHub — automatic)

Fetched live from the repository URL when you click **Predict Risk**
(unless a sample preset is active).

| Feature | Source | How it is calculated |
|---|---|---|
| `total_commits` | 🐙 GitHub | Total number of commits on the default branch (`/commits`, counted via pagination) |
| `weekly_commits` | 🐙 GitHub | Commits in the last 7 days (`/commits?since=<7 days ago>`) |
| `inactive_days` | 🐙 GitHub | Days since the most recent commit's author date |
| `bug_count` | 🐙 GitHub | Open issues carrying a `bug` label (pull requests excluded) |
| `high_priority_bugs` | 🐙 GitHub | Open issues labelled `high`, `critical`, or `priority: high` |

### Delivery (manual, or overridden by Jira)

Typed in the form, **but if a Jira Project Key is set they are replaced by live
Jira values** at predict time (and the "Fetch from Jira" button previews them).

| Feature | Source | How Jira calculates it |
|---|---|---|
| `overdue_tasks` | 🖊 / 🟦 | Tasks that are **not Done** and whose due date is before today |
| `delay_count` | 🖊 / 🟦 | Tasks completed **after** their due date **+** tasks currently overdue |
| `task_completion_rate` | 🖊 / 🟦 | `done tasks ÷ total tasks × 100` |
| `progress_percentage` | 🖊 / 🟦 | `(done + 0.5 × in-progress) ÷ total × 100` — in-progress work counts as half done |

Task states come from Jira status categories: **Done** (`done`),
**In Progress** (`indeterminate`), **To Do** (`new`).

### Team Quality (manual on this page; auto-derived on the Dashboard)

| Feature | Risk page | Dashboard derivation |
|---|---|---|
| `code_quality_score` | 🖊 Manual | ⚙ Team PR acceptance rate: `merged PRs ÷ opened PRs × 100` |
| `collaboration_score` | 🖊 Manual | ⚙ Average of every member's Collaboration component (see §2) |
| `overall_ci_score` | 🖊 Manual | ⚙ Team average Contribution Index (see §2) |

> **Note:** PR acceptance rate is a *proxy* for code quality (how often the team's
> work is accepted on review). A static-analysis integration (e.g. SonarQube) would
> be the rigorous replacement — listed as future work.

---

## 2. Contribution Index (per member)

Every human contributor (bots are filtered out) gets a CI score of 0–100 built from
five weighted components:

| Component | Weight | Raw data (per member) | Scoring |
|---|---|---|---|
| Commit Activity | 30% | commits authored | relative to team max |
| Task Completion | 25% | pull requests **merged** | relative to team max |
| Collaboration | 20% | issue comments + review comments + issues opened | relative to team max |
| Issue Resolution | 15% | issues closed (credited to **assignees**, falling back to the author) | relative to team max |
| Code Quality | 10% | own merged PRs ÷ own opened PRs × 100 | absolute rate |

**Relative to team max** means the member with the highest raw value scores 100 and
everyone else scores proportionally (`value ÷ max × 100`), so scores are comparable
within a team regardless of project size.

```
CI = Σ (component score × weight) ÷ Σ (active weights)
```

**Renormalization:** if the whole team produced no data for a component (e.g. a team
that never opens PRs), that component is dropped and the remaining weights are
rescaled — a warning explains this on screen.

**Contribution share** = `member CI ÷ sum of all CIs × 100` (shown as "% of team
contribution").

**Team Average CI** = mean CI across all members — this is what the Dashboard feeds
into the risk model as `overall_ci_score`.

### Raw data sources (GitHub REST API)

| Raw metric | Endpoint |
|---|---|
| Commits per member | `/repos/{o}/{r}/contributors` (contribution counts) |
| PRs opened / merged | `/repos/{o}/{r}/pulls?state=all` (merged = has `merged_at`) |
| Issues opened / resolved | `/repos/{o}/{r}/issues?state=all` (PRs excluded) |
| Issue comments | `/repos/{o}/{r}/issues/comments` |
| Code-review comments | `/repos/{o}/{r}/pulls/comments` |

Excluded bot accounts: any login ending in `[bot]`, plus `dependabot`, `coveralls`,
`codecov`, `github-actions`, `renovate`, `pre-commit-ci`, `snyk-bot`.

---

## 3. Jira Task Contribution (per assignee)

| Field | How it is calculated |
|---|---|
| Assigned | issues where the person is the assignee (`Unassigned` bucket otherwise) |
| Completed | their issues with status category Done |
| In Progress / Overdue / Completed Late | classified per issue exactly as in §1 Delivery |
| **Task Score** | `own completed ÷ team max completed × 100` (relative, like CI components) |
| **On-time rate** | `(completed − completed late) ÷ completed × 100` |

---

## 4. Dashboard extras

| Field | How it gets its value |
|---|---|
| Risk Status tile | The ML model's prediction run on the 12 features — all derived live (GitHub activity + Jira delivery + §1 Team Quality derivations); no manual input |
| Commit Activity chart | `/repos/{o}/{r}/stats/commit_activity` — commits per week, last 52 weeks (GitHub may answer "still computing" on first request) |
| Updated (live/cached) | Server caches each project's data for **120 s**; auto-refresh polls every **60 s**; "Refresh Now" bypasses the cache |

### Alert rules

| Alert | Trigger |
|---|---|
| 🔴 Predicted HIGH RISK | model output = High Risk |
| 🟠 Predicted MEDIUM RISK | model output = Medium Risk |
| 🔴 No commits for N days | `inactive_days > 14` |
| 🟠 No commits in the last 7 days | `weekly_commits == 0` |
| 🔴 High-priority bugs open | `high_priority_bugs > 0` |
| 🟠 Tasks past due date | Jira `overdue_tasks > 0` |
| 🟠 Tasks completed late | Jira late completions `> 0` |
| 🟠 Uneven participation | top member's contribution share `> 60%` |
| 🟢 No active risk alerts | none of the above fired |

---

## 5. Where each formula lives in the code

| Metric group | File |
|---|---|
| GitHub repo-level metrics (commits, bugs) | `main.py` → `get_github_metrics()` |
| Contribution Index | `contribution.py` → `compute_contribution_index()` |
| Jira project metrics | `jira_client.py` → `compute_project_metrics()` |
| Jira per-assignee stats | `jira_client.py` → `compute_member_task_stats()` |
| Dashboard derivations & alerts | `main.py` → `build_dashboard_data()`, `build_dashboard_alerts()` |
| ML model features & prediction | `main.py` → `FEATURE_COLUMNS`, `/predict`, `best_risk_prediction_model.pkl` |
