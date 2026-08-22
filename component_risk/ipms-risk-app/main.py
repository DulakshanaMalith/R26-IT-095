from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import joblib
import pandas as pd
import requests
from datetime import datetime, timedelta
from pathlib import Path
import re

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent

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

    headers = {
        "Accept": "application/vnd.github+json"
    }

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


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": None,
            "form_data": DEFAULT_FORM_DATA
        }
    )


@app.post("/predict")
def predict_risk(
    request: Request,
    project_name: str = Form(...),
    team_id: str = Form(...),
    github_url: str = Form(...),
    sample_profile: str = Form(""),
    overdue_tasks: int = Form(...),
    task_completion_rate: float = Form(...),
    code_quality_score: float = Form(...),
    collaboration_score: float = Form(...),
    overall_ci_score: float = Form(...),
    progress_percentage: float = Form(...),
    delay_count: int = Form(...)
):
    github_metrics = SAMPLE_GITHUB_METRICS.get(sample_profile) or get_github_metrics(github_url)
    form_data = {
        "sample_profile": sample_profile,
        "project_name": project_name,
        "team_id": team_id,
        "github_url": github_url,
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

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "form_data": form_data,
            "result": {
                "project_name": project_name,
                "team_id": team_id,
                "risk_status": risk_status,
                "features": input_data
            }
        }
    )
