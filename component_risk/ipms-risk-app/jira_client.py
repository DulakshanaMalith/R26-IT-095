import os
import re
from datetime import date, datetime

import requests

ISSUE_FIELDS = "summary,status,assignee,duedate,priority,created,resolutiondate,issuetype"

CONFIG_HELP = (
    "Jira is not configured. Set the JIRA_BASE_URL (e.g. https://yourteam.atlassian.net), "
    "JIRA_EMAIL and JIRA_API_TOKEN environment variables."
)


def get_config():
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    return base_url, email, token


def is_configured():
    return all(get_config())


def is_valid_project_key(project_key):
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_]*$", project_key))


def parse_due_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_datetime(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def fetch_project_issues(project_key):
    base_url, email, token = get_config()

    if not (base_url and email and token):
        return [], CONFIG_HELP

    if not is_valid_project_key(project_key):
        return [], "Invalid Jira project key."

    issues = []
    next_page_token = None

    while True:
        params = {
            "jql": f'project = "{project_key}" ORDER BY created ASC',
            "fields": ISSUE_FIELDS,
            "maxResults": 100
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        try:
            response = requests.get(
                f"{base_url}/rest/api/3/search/jql",
                params=params,
                auth=(email, token),
                timeout=20
            )
        except requests.RequestException:
            return issues, "Network error while contacting Jira."

        if response.status_code == 401:
            return [], "Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN."

        if response.status_code == 400:
            return [], f"Jira project '{project_key}' was not found or is not accessible."

        if response.status_code != 200:
            return [], f"Jira returned status {response.status_code}."

        data = response.json()
        issues.extend(data.get("issues", []))

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return issues, None


def classify_issue(fields, today):
    """Returns (status_category, is_overdue, was_completed_late) for one issue."""
    status = fields.get("status") or {}
    category = (status.get("statusCategory") or {}).get("key", "new")

    due = parse_due_date(fields.get("duedate"))

    is_overdue = False
    completed_late = False

    if due:
        if category == "done":
            resolved = parse_datetime(fields.get("resolutiondate"))
            if resolved and resolved.date() > due:
                completed_late = True
        elif due < today:
            is_overdue = True

    return category, is_overdue, completed_late


def compute_project_metrics(issues):
    today = date.today()

    total = len(issues)
    done = 0
    in_progress = 0
    todo = 0
    overdue = 0
    delays = 0

    for issue in issues:
        fields = issue.get("fields") or {}
        category, is_overdue, completed_late = classify_issue(fields, today)

        if category == "done":
            done += 1
        elif category == "indeterminate":
            in_progress += 1
        else:
            todo += 1

        if is_overdue:
            overdue += 1

        # A delay is a task finished after its due date or still open past it.
        if completed_late or is_overdue:
            delays += 1

    completion_rate = round(done / total * 100, 2) if total else 0.0
    # Progress counts in-progress work as half done.
    progress = round((done + 0.5 * in_progress) / total * 100, 2) if total else 0.0

    return {
        "total_tasks": total,
        "completed_tasks": done,
        "in_progress_tasks": in_progress,
        "todo_tasks": todo,
        "overdue_tasks": overdue,
        "delay_count": delays,
        "task_completion_rate": completion_rate,
        "progress_percentage": progress
    }


def compute_member_task_stats(issues):
    today = date.today()
    members = {}

    for issue in issues:
        fields = issue.get("fields") or {}
        assignee = fields.get("assignee") or {}
        name = assignee.get("displayName") or "Unassigned"

        member = members.setdefault(name, {
            "assigned": 0,
            "completed": 0,
            "in_progress": 0,
            "overdue": 0,
            "completed_late": 0
        })

        category, is_overdue, completed_late = classify_issue(fields, today)

        member["assigned"] += 1
        if category == "done":
            member["completed"] += 1
        elif category == "indeterminate":
            member["in_progress"] += 1
        if is_overdue:
            member["overdue"] += 1
        if completed_late:
            member["completed_late"] += 1

    max_completed = max(
        (member["completed"] for member in members.values()),
        default=0
    )

    rows = []
    for name, member in members.items():
        task_score = (
            round(member["completed"] / max_completed * 100, 1)
            if max_completed > 0
            else 0.0
        )
        on_time_rate = (
            round(
                (member["completed"] - member["completed_late"])
                / member["completed"] * 100,
                1
            )
            if member["completed"] > 0
            else 0.0
        )

        rows.append({
            "name": name,
            "stats": member,
            "task_score": task_score,
            "on_time_rate": on_time_rate
        })

    rows.sort(key=lambda row: (row["task_score"], row["stats"]["assigned"]), reverse=True)
    return rows


def get_jira_analytics(project_key):
    issues, error = fetch_project_issues(project_key)

    if error:
        return {"error": error, "project_key": project_key, "metrics": None, "members": []}

    if not issues:
        return {
            "error": f"No issues found in Jira project '{project_key}'.",
            "project_key": project_key,
            "metrics": None,
            "members": []
        }

    return {
        "error": None,
        "project_key": project_key,
        "metrics": compute_project_metrics(issues),
        "members": compute_member_task_stats(issues)
    }
