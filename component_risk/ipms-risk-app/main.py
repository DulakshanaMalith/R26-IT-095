from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import joblib
import pandas as pd
import requests
from datetime import datetime, timedelta
from pathlib import Path
import os
import re
import threading
import time

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load credentials (JIRA_*, GITHUB_TOKEN) from the app's .env file
# before any module reads them from the environment.
load_dotenv(BASE_DIR / ".env")

from contribution import build_headers, compute_contribution_index
from jira_client import compute_project_metrics, fetch_project_issues, get_jira_analytics
import auth
import database
import emailer
import risk_monitor

app = FastAPI()

# Create the SQLite tables on first run.
database.init_db()

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Load ML model and scaler
model = joblib.load(BASE_DIR / "best_risk_prediction_model.pkl")
scaler = joblib.load(BASE_DIR / "scaler.pkl")

FEATURE_COLUMNS = [
    "total_commits",
    "weekly_commits",
    "inactive_days",
    "overdue_tasks",
    "bug_count",
    "high_priority_bugs",
    "task_completion_rate",
    "code_quality_score",
    "collaboration_score",
    "overall_ci_score",
    "progress_percentage",
    "delay_count"
]

LABEL_MAP = {
    0: "High Risk",
    1: "Low Risk",
    2: "Medium Risk"
}

SAMPLE_GITHUB_METRICS = {
    "high": {
        "total_commits": 2,
        "weekly_commits": 0,
        "inactive_days": 45,
        "bug_count": 15,
        "high_priority_bugs": 6
    },
    "medium": {
        "total_commits": 65,
        "weekly_commits": 4,
        "inactive_days": 6,
        "bug_count": 6,
        "high_priority_bugs": 2
    },
    "low": {
        "total_commits": 420,
        "weekly_commits": 35,
        "inactive_days": 1,
        "bug_count": 1,
        "high_priority_bugs": 0
    }
}

DEFAULT_FORM_DATA = {
    "sample_profile": "medium",
    "project_name": "Student Portal Upgrade",
    "team_id": "TEAM-101",
    "github_url": "https://github.com/ipms-samples/medium-risk-demo",
    "jira_project_key": "",
    "overdue_tasks": 4,
    "delay_count": 3,
    "task_completion_rate": 63.00,
    "progress_percentage": 58.00,
    "code_quality_score": 68.00,
    "collaboration_score": 61.00,
    "overall_ci_score": 64.00
}


def extract_github_owner_repo(github_url):
    pattern = r"github\.com/([^/]+)/([^/]+)"
    match = re.search(pattern, github_url)

    if not match:
        return None, None

    owner = match.group(1)
    repo = match.group(2).replace(".git", "")

    return owner, repo


def get_paginated_count(url, headers, params=None):
    params = dict(params or {})
    params["per_page"] = 1

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException:
        return 0

    if response.status_code != 200:
        return 0

    if "last" in response.links:
        page_match = re.search(r"[?&]page=(\d+)", response.links["last"]["url"])
        if page_match:
            return int(page_match.group(1))

    return len(response.json())


def get_latest_commit_date(url, headers):
    try:
        response = requests.get(url, headers=headers, params={"per_page": 1}, timeout=10)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    commits = response.json()
    if not commits:
        return None

    date_str = commits[0].get("commit", {}).get("author", {}).get("date")
    if not date_str:
        return None

    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")


def get_all_paginated_items(url, headers, params=None):
    items = []
    page = 1

    while True:
        page_params = dict(params or {})
        page_params.update({
            "per_page": 100,
            "page": page
        })

        try:
            response = requests.get(url, headers=headers, params=page_params, timeout=10)
        except requests.RequestException:
            break

        if response.status_code != 200:
            break

        page_items = response.json()
        items.extend(page_items)

        if "next" not in response.links:
            break

        page += 1

    return items


def get_github_metrics(github_url):
    owner, repo = extract_github_owner_repo(github_url)

    if owner is None or repo is None:
        return {
            "total_commits": 0,
            "weekly_commits": 0,
            "inactive_days": 0,
            "bug_count": 0,
            "high_priority_bugs": 0
        }

    headers = build_headers()

    commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    issues_url = f"https://api.github.com/repos/{owner}/{repo}/issues"

    one_week_ago = datetime.now() - timedelta(days=7)
    one_week_ago_iso = one_week_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    total_commits = get_paginated_count(commits_url, headers)
    weekly_commits = get_paginated_count(
        commits_url,
        headers,
        params={"since": one_week_ago_iso}
    )

    inactive_days = 0
    latest_commit = get_latest_commit_date(commits_url, headers)
    if latest_commit:
        inactive_days = (datetime.now() - latest_commit).days

    bug_count = 0
    high_priority_bugs = 0

    issues = get_all_paginated_items(issues_url, headers)

    for issue in issues:
        # The issues endpoint also returns pull requests; skip them.
        if "pull_request" in issue:
            continue

        labels = [label["name"].lower() for label in issue.get("labels", [])]

        if "bug" in labels:
            bug_count += 1

        if "high" in labels or "critical" in labels or "priority: high" in labels:
            high_priority_bugs += 1

    return {
        "total_commits": total_commits,
        "weekly_commits": weekly_commits,
        "inactive_days": inactive_days,
        "bug_count": bug_count,
        "high_priority_bugs": high_priority_bugs
    }


def resolve_analysis_target(user, project_id, github_url, jira_project_key):
    """Decides which repo / Jira project this user is allowed to analyse.

    Returns (github_url, jira_project_key, project, error). Students are
    restricted to projects they belong to; supervisors may also analyse an
    arbitrary repository they type in.
    """
    project = auth.resolve_project(user, project_id)

    if project:
        return project["github_url"], project["jira_project_key"], project, None

    if user["role"] == "supervisor":
        return github_url.strip(), jira_project_key.strip(), None, None

    return "", "", None, (
        "Students can only view their own assigned project. "
        "Pick a project from My Projects."
    )


@app.get("/")
def home(request: Request, project_id: int = 0):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    form_data = dict(DEFAULT_FORM_DATA)
    project = auth.resolve_project(user, project_id)

    if project:
        form_data.update({
            "sample_profile": "",
            "project_name": project["name"],
            "team_id": project["team_id"],
            "github_url": project["github_url"],
            "jira_project_key": project["jira_project_key"]
        })

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": None,
            "form_data": form_data,
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user)
        }
    )


@app.get("/contribution")
def contribution_page(request: Request, project_id: int = 0):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    project = auth.resolve_project(user, project_id)

    return templates.TemplateResponse(
        request=request,
        name="contribution.html",
        context={
            "analysis": None,
            "github_url": project["github_url"] if project else "",
            "jira_project_key": project["jira_project_key"] if project else "",
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user)
        }
    )


@app.post("/contribution")
def analyze_contribution(
    request: Request,
    github_url: str = Form(""),
    jira_project_key: str = Form(""),
    project_id: int = Form(0)
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    github_url, jira_project_key, project, error = resolve_analysis_target(
        user, project_id, github_url, jira_project_key
    )

    if error:
        analysis = {"error": error, "members": [], "warnings": [], "jira": None}
    else:
        analysis = compute_contribution_index(github_url)
        analysis["jira"] = get_jira_analytics(jira_project_key) if jira_project_key else None

    return templates.TemplateResponse(
        request=request,
        name="contribution.html",
        context={
            "analysis": analysis,
            "github_url": github_url,
            "jira_project_key": jira_project_key,
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user)
        }
    )


def get_weekly_commit_activity(github_url):
    owner, repo = extract_github_owner_repo(github_url)
    if owner is None:
        return []

    url = f"https://api.github.com/repos/{owner}/{repo}/stats/commit_activity"
    try:
        response = requests.get(url, headers=build_headers(), timeout=15)
    except requests.RequestException:
        return []

    # GitHub returns 202 while it computes statistics for the repo.
    if response.status_code != 200:
        return []

    data = response.json()
    if not isinstance(data, list):
        return []

    return [
        {"week": week.get("week", 0), "total": week.get("total", 0)}
        for week in data
    ]


def build_dashboard_alerts(risk_status, github_metrics, jira_metrics, members):
    alerts = []

    if risk_status == "High Risk":
        alerts.append({
            "level": "critical",
            "message": "Project is predicted HIGH RISK — supervisor intervention recommended."
        })
    elif risk_status == "Medium Risk":
        alerts.append({
            "level": "warning",
            "message": "Project is predicted MEDIUM RISK — monitor progress closely."
        })

    if github_metrics["inactive_days"] > 14:
        alerts.append({
            "level": "critical",
            "message": f"No commits for {github_metrics['inactive_days']} days."
        })
    elif github_metrics["weekly_commits"] == 0:
        alerts.append({
            "level": "warning",
            "message": "No commits in the last 7 days."
        })

    if github_metrics["high_priority_bugs"] > 0:
        alerts.append({
            "level": "critical",
            "message": f"{github_metrics['high_priority_bugs']} high-priority bug(s) open on GitHub."
        })

    if jira_metrics:
        if jira_metrics["overdue_tasks"] > 0:
            alerts.append({
                "level": "warning",
                "message": f"{jira_metrics['overdue_tasks']} task(s) past their due date in Jira."
            })
        if jira_metrics["delay_count"] > jira_metrics["overdue_tasks"]:
            late = jira_metrics["delay_count"] - jira_metrics["overdue_tasks"]
            alerts.append({
                "level": "warning",
                "message": f"{late} task(s) were completed after their due date."
            })

    if members:
        top = members[0]
        if top["share"] > 60:
            alerts.append({
                "level": "warning",
                "message": (
                    f"Uneven participation: {top['login']} accounts for "
                    f"{top['share']}% of team contribution."
                )
            })

    if not alerts:
        alerts.append({
            "level": "ok",
            "message": "No active risk alerts — project activity looks healthy."
        })

    return alerts


def get_github_rate_remaining():
    try:
        response = requests.get(
            "https://api.github.com/rate_limit",
            headers=build_headers(),
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["resources"]["core"]["remaining"]
    except (requests.RequestException, KeyError, ValueError):
        pass
    return None


def build_dashboard_data(github_url, jira_project_key):
    rate_remaining = get_github_rate_remaining()
    contribution = compute_contribution_index(github_url)
    github_metrics = get_github_metrics(github_url)
    weekly_activity = get_weekly_commit_activity(github_url)
    jira = get_jira_analytics(jira_project_key) if jira_project_key else None

    warnings = list(contribution.get("warnings") or [])
    if contribution.get("error"):
        warnings.append(contribution["error"])

    if rate_remaining is not None and rate_remaining < 20:
        warnings.append(
            f"GitHub API rate limit nearly exhausted ({rate_remaining} requests left) — "
            "GitHub metrics may show as 0. Add a GITHUB_TOKEN to .env for a 5,000/hour limit."
        )

    members = contribution.get("members") or []
    team = contribution.get("team") or {}

    # Derive the team-quality features from live data instead of manual input.
    overall_ci = team.get("average_ci", 0.0)
    collaboration_score = (
        round(sum(m["scores"]["collaboration"] for m in members) / len(members), 1)
        if members else 0.0
    )
    total_prs_opened = sum(m["stats"]["prs_opened"] for m in members)
    total_prs_merged = sum(m["stats"]["prs_merged"] for m in members)
    code_quality_score = (
        round(total_prs_merged / total_prs_opened * 100, 1)
        if total_prs_opened else 0.0
    )

    jira_metrics = None
    if jira:
        if jira.get("error"):
            warnings.append(jira["error"])
        else:
            jira_metrics = jira["metrics"]
    else:
        warnings.append("No Jira project key provided — delivery metrics default to 0.")

    if not emailer.is_configured():
        warnings.append(
            "Automatic risk emails are disabled — set SMTP_HOST, SMTP_USERNAME and "
            "SMTP_PASSWORD in .env to enable them."
        )

    delivery = jira_metrics or {
        "total_tasks": 0,
        "completed_tasks": 0,
        "in_progress_tasks": 0,
        "todo_tasks": 0,
        "overdue_tasks": 0,
        "delay_count": 0,
        "task_completion_rate": 0.0,
        "progress_percentage": 0.0
    }

    input_data = {
        "total_commits": github_metrics["total_commits"],
        "weekly_commits": github_metrics["weekly_commits"],
        "inactive_days": github_metrics["inactive_days"],
        "overdue_tasks": delivery["overdue_tasks"],
        "bug_count": github_metrics["bug_count"],
        "high_priority_bugs": github_metrics["high_priority_bugs"],
        "task_completion_rate": delivery["task_completion_rate"],
        "code_quality_score": code_quality_score,
        "collaboration_score": collaboration_score,
        "overall_ci_score": overall_ci,
        "progress_percentage": delivery["progress_percentage"],
        "delay_count": delivery["delay_count"]
    }

    risk_status = None
    try:
        df = pd.DataFrame([input_data], columns=FEATURE_COLUMNS)
        prediction = model.predict(scaler.transform(df))[0]
        risk_status = LABEL_MAP.get(prediction, str(prediction))
    except Exception:
        warnings.append("Risk prediction failed for the derived feature set.")

    return {
        "generated_at": datetime.now().strftime("%H:%M:%S"),
        "repo": contribution.get("repo"),
        "risk_status": risk_status,
        "github": {**github_metrics, "weekly_activity": weekly_activity},
        "delivery": delivery,
        "jira_available": jira_metrics is not None,
        "jira_members": (jira or {}).get("members") or [],
        "team": {
            "average_ci": overall_ci,
            "collaboration_score": collaboration_score,
            "code_quality_score": code_quality_score,
            "member_count": team.get("member_count", 0)
        },
        "members": [
            {
                "login": m["login"],
                "ci": m["ci"],
                "share": m["share"],
                "commits": m["stats"]["commits"]
            }
            for m in members
        ],
        "alerts": build_dashboard_alerts(risk_status, github_metrics, jira_metrics, members),
        "warnings": list(dict.fromkeys(warnings))
    }


DASHBOARD_CACHE = {}
DASHBOARD_CACHE_TTL_SECONDS = 120


@app.get("/dashboard")
def dashboard_page(
    request: Request,
    github_url: str = "",
    jira_project_key: str = "",
    project_id: int = 0
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    github_url, jira_project_key, project, error = resolve_analysis_target(
        user, project_id, github_url, jira_project_key
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "github_url": github_url,
            "jira_project_key": jira_project_key,
            "access_error": error,
            "project_id": project_id,
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user)
        }
    )


@app.get("/api/dashboard-data")
def dashboard_data(
    request: Request,
    github_url: str = "",
    jira_project_key: str = "",
    force: int = 0,
    project_id: int = 0
):
    user = auth.current_user(request)
    if user is None:
        return {"error": "Not signed in.", "alerts": [], "warnings": ["Please sign in again."]}

    github_url, jira_project_key, _project, access_error = resolve_analysis_target(
        user, project_id, github_url, jira_project_key
    )
    if access_error:
        return {"error": access_error, "alerts": [], "warnings": [access_error]}

    cache_key = (github_url.strip(), jira_project_key.strip())
    now = time.time()

    entry = DASHBOARD_CACHE.get(cache_key)
    if entry and not force and now - entry[0] < DASHBOARD_CACHE_TTL_SECONDS:
        data = dict(entry[1])
        data["cached"] = True
        return data

    data = build_dashboard_data(*cache_key)
    data["cached"] = False
    DASHBOARD_CACHE[cache_key] = (now, data)

    # Automatic risk email when a registered project becomes at-risk.
    if _project is not None:
        try:
            risk_monitor.evaluate_project_risk(_project, data.get("risk_status"), data)
        except Exception:
            pass

    return data


@app.get("/api/jira-metrics")
def jira_metrics(request: Request, project_key: str):
    user = auth.current_user(request)
    if user is None:
        return {"error": "Not signed in.", "metrics": None}

    issues, error = fetch_project_issues(project_key.strip())

    if error:
        return {"error": error, "metrics": None}

    if not issues:
        return {"error": f"No issues found in Jira project '{project_key}'.", "metrics": None}

    return {"error": None, "metrics": compute_project_metrics(issues)}


@app.post("/predict")
def predict_risk(
    request: Request,
    project_name: str = Form(...),
    team_id: str = Form(...),
    github_url: str = Form(""),
    jira_project_key: str = Form(""),
    project_id: int = Form(0),
    sample_profile: str = Form(""),
    overdue_tasks: int = Form(...),
    task_completion_rate: float = Form(...),
    code_quality_score: float = Form(...),
    collaboration_score: float = Form(...),
    overall_ci_score: float = Form(...),
    progress_percentage: float = Form(...),
    delay_count: int = Form(...)
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    github_url, jira_project_key, project, access_error = resolve_analysis_target(
        user, project_id, github_url, jira_project_key
    )
    if access_error:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": None,
                "form_data": dict(DEFAULT_FORM_DATA),
                "access_error": access_error,
                "user": user,
                "project": None,
                "projects": auth.visible_projects(user)
            }
        )

    github_metrics = SAMPLE_GITHUB_METRICS.get(sample_profile) or get_github_metrics(github_url)

    # When a Jira project key is provided, delivery metrics come from Jira
    # and override the manually entered values.
    jira_project_key = jira_project_key.strip()
    jira_warning = None
    jira_used = False

    if jira_project_key and not sample_profile:
        issues, jira_error = fetch_project_issues(jira_project_key)

        if jira_error:
            jira_warning = jira_error
        elif not issues:
            jira_warning = f"No issues found in Jira project '{jira_project_key}'."
        else:
            jira = compute_project_metrics(issues)
            overdue_tasks = jira["overdue_tasks"]
            delay_count = jira["delay_count"]
            task_completion_rate = jira["task_completion_rate"]
            progress_percentage = jira["progress_percentage"]
            jira_used = True

    form_data = {
        "sample_profile": sample_profile,
        "project_name": project_name,
        "team_id": team_id,
        "github_url": github_url,
        "jira_project_key": jira_project_key,
        "overdue_tasks": overdue_tasks,
        "delay_count": delay_count,
        "task_completion_rate": task_completion_rate,
        "progress_percentage": progress_percentage,
        "code_quality_score": code_quality_score,
        "collaboration_score": collaboration_score,
        "overall_ci_score": overall_ci_score
    }

    input_data = {
        "total_commits": github_metrics["total_commits"],
        "weekly_commits": github_metrics["weekly_commits"],
        "inactive_days": github_metrics["inactive_days"],
        "overdue_tasks": overdue_tasks,
        "bug_count": github_metrics["bug_count"],
        "high_priority_bugs": github_metrics["high_priority_bugs"],
        "task_completion_rate": task_completion_rate,
        "code_quality_score": code_quality_score,
        "collaboration_score": collaboration_score,
        "overall_ci_score": overall_ci_score,
        "progress_percentage": progress_percentage,
        "delay_count": delay_count
    }

    df = pd.DataFrame([input_data], columns=FEATURE_COLUMNS)

    scaled_data = scaler.transform(df)

    prediction = model.predict(scaled_data)[0]

    risk_status = LABEL_MAP.get(prediction, str(prediction))

    # Automatic risk email when a registered project becomes at-risk.
    if project is not None:
        try:
            risk_monitor.evaluate_project_risk(project, risk_status, None)
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user),
            "form_data": form_data,
            "result": {
                "project_name": project_name,
                "team_id": team_id,
                "risk_status": risk_status,
                "features": input_data,
                "jira_used": jira_used,
                "jira_project_key": jira_project_key,
                "jira_warning": jira_warning
            }
        }
    )


# =========================================================================
# Authentication: register, login, logout
# =========================================================================

@app.get("/register")
def register_page(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/projects", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None, "form": {}}
    )


@app.post("/register")
def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...)
):
    error = auth.validate_registration(email, full_name, password, role)

    if error:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": error,
                "form": {"full_name": full_name, "email": email, "role": role}
            }
        )

    auth.register_user(email, full_name, password, role)
    token, login_error = auth.login(email, password)

    if login_error:
        return RedirectResponse("/login", status_code=303)

    response = RedirectResponse("/projects", status_code=303)
    auth.set_session_cookie(response, token)
    return response


@app.get("/login")
def login_page(request: Request):
    if auth.current_user(request):
        return RedirectResponse("/projects", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "email": ""}
    )


@app.post("/login")
def login_submit(request: Request, email: str = Form(...), password: str = Form(...)):
    token, error = auth.login(email, password)

    if error:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": error, "email": email}
        )

    response = RedirectResponse("/projects", status_code=303)
    auth.set_session_cookie(response, token)
    return response


@app.get("/logout")
def logout(request: Request):
    auth.logout(request.cookies.get(auth.SESSION_COOKIE))
    response = RedirectResponse("/login", status_code=303)
    auth.clear_session_cookie(response)
    return response


# =========================================================================
# Projects: the role-aware landing page
# =========================================================================

@app.get("/projects")
def projects_page(request: Request, message: str = ""):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "user": user,
            "projects": auth.visible_projects(user),
            "message": message
        }
    )


@app.post("/projects/new")
def create_project(
    request: Request,
    name: str = Form(...),
    team_id: str = Form(...),
    github_url: str = Form(""),
    jira_project_key: str = Form("")
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    # Only supervisors may create projects.
    if user["role"] != "supervisor":
        return RedirectResponse(
            "/projects?message=Only+supervisors+can+create+projects.", status_code=303
        )

    database.create_project(name, team_id, github_url, jira_project_key, user["id"])
    return RedirectResponse("/projects?message=Project+created.", status_code=303)


@app.get("/projects/{project_id}")
def project_detail(request: Request, project_id: int, message: str = ""):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    project = auth.resolve_project(user, project_id)
    if project is None:
        return RedirectResponse(
            "/projects?message=You+do+not+have+access+to+that+project.", status_code=303
        )

    supervisor = database.get_user_by_id(project["supervisor_id"])
    assigned = database.list_members(project_id)
    assigned_ids = {member["id"] for member in assigned}

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "user": user,
            "project": project,
            "projects": auth.visible_projects(user),
            "supervisor": supervisor,
            "members": assigned,
            "available_students": [
                student for student in database.list_students()
                if student["id"] not in assigned_ids
            ],
            "message": message
        }
    )


@app.post("/projects/{project_id}/edit")
def edit_project(
    request: Request,
    project_id: int,
    name: str = Form(...),
    team_id: str = Form(...),
    github_url: str = Form(""),
    jira_project_key: str = Form("")
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    project = auth.resolve_project(user, project_id)
    if project is None or user["role"] != "supervisor":
        return RedirectResponse(
            "/projects?message=Only+the+supervisor+can+edit+this+project.", status_code=303
        )

    database.update_project(project_id, name, team_id, github_url, jira_project_key)
    return RedirectResponse(f"/projects/{project_id}?message=Project+updated.", status_code=303)


@app.post("/projects/{project_id}/members")
def add_project_member(
    request: Request,
    project_id: int,
    user_id: int = Form(...),
    github_login: str = Form(""),
    jira_name: str = Form("")
):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    project = auth.resolve_project(user, project_id)
    if project is None or user["role"] != "supervisor":
        return RedirectResponse(
            "/projects?message=Only+the+supervisor+can+manage+members.", status_code=303
        )

    database.add_member(project_id, user_id, github_login, jira_name)
    return RedirectResponse(f"/projects/{project_id}?message=Member+added.", status_code=303)


@app.post("/projects/{project_id}/members/remove")
def remove_project_member(request: Request, project_id: int, user_id: int = Form(...)):
    user = auth.current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    project = auth.resolve_project(user, project_id)
    if project is None or user["role"] != "supervisor":
        return RedirectResponse(
            "/projects?message=Only+the+supervisor+can+manage+members.", status_code=303
        )

    database.remove_member(project_id, user_id)
    return RedirectResponse(f"/projects/{project_id}?message=Member+removed.", status_code=303)


# =========================================================================
# Background risk monitor: checks every registered project on an interval
# and emails the team when one becomes at-risk (even if nobody is watching).
# =========================================================================

def risk_monitor_loop():
    try:
        interval_minutes = max(int(os.environ.get("RISK_CHECK_INTERVAL_MINUTES", "60")), 5)
    except ValueError:
        interval_minutes = 60

    # Small delay so restarts don't immediately spend API rate limit.
    time.sleep(120)

    while True:
        for project in database.list_projects_with_repo():
            try:
                data = build_dashboard_data(
                    project["github_url"], project["jira_project_key"]
                )
                risk_monitor.evaluate_project_risk(
                    project, data.get("risk_status"), data
                )
            except Exception:
                pass

        time.sleep(interval_minutes * 60)


@app.on_event("startup")
def start_risk_monitor():
    if emailer.is_configured() and os.environ.get("RISK_MONITOR_ENABLED", "1") != "0":
        threading.Thread(target=risk_monitor_loop, daemon=True).start()


@app.post("/api/test-email")
def send_test_email(request: Request):
    """Lets a supervisor confirm the SMTP settings by emailing themselves."""
    user = auth.current_user(request)
    if user is None or user["role"] != "supervisor":
        return {"error": "Only signed-in supervisors can send a test email.", "sent_to": None}

    if not emailer.is_configured():
        return {
            "error": "Email is not configured. Set SMTP_HOST, SMTP_USERNAME and "
                     "SMTP_PASSWORD in .env, then restart the server.",
            "sent_to": None
        }

    error = emailer.send_email(
        [user["email"]],
        "[IPMS] Test email",
        "This is a test email from the Intelligent Project Management System.\n"
        "If you received this, automatic risk alerts are working."
    )
    return {"error": error, "sent_to": None if error else user["email"]}
