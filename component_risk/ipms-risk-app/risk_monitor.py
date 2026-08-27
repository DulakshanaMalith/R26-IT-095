"""Automatic risk alerts.

When a registered project's predicted risk becomes one of ALERT_LEVELS,
every team member and the supervisor receive an email. Cooldowns prevent
repeated emails while the project stays at risk.
"""
import os
from datetime import datetime, timedelta

import database
import emailer

# Predicted statuses that trigger an email.
ALERT_LEVELS = {"High Risk"}


def get_cooldown_hours():
    try:
        return max(int(os.environ.get("RISK_ALERT_COOLDOWN_HOURS", "24")), 1)
    except ValueError:
        return 24


def get_app_base_url():
    return os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")


def build_alert_email(project, risk_status, data):
    subject = f"[IPMS] {project['name']} is {risk_status.upper()}"

    lines = [
        f"Project        : {project['name']} (Team {project['team_id']})",
        f"Predicted risk : {risk_status}",
        ""
    ]

    data = data or {}
    delivery = data.get("delivery") or {}
    github = data.get("github") or {}
    team = data.get("team") or {}

    if delivery:
        lines += [
            f"Progress          : {delivery.get('progress_percentage', '-')}%",
            f"Task completion   : {delivery.get('task_completion_rate', '-')}%",
            f"Overdue tasks     : {delivery.get('overdue_tasks', '-')}",
            f"Delays            : {delivery.get('delay_count', '-')}"
        ]
    if github:
        lines += [
            f"Commits this week : {github.get('weekly_commits', '-')}",
            f"Inactive days     : {github.get('inactive_days', '-')}"
        ]
    if team:
        lines.append(f"Team average CI   : {team.get('average_ci', '-')}")

    messages = [
        alert.get("message")
        for alert in data.get("alerts") or []
        if alert.get("level") in ("critical", "warning")
    ]
    if messages:
        lines += ["", "Active alerts:"] + [f"  - {message}" for message in messages]

    lines += [
        "",
        "Open the live dashboard:",
        f"{get_app_base_url()}/dashboard?project_id={project['id']}",
        "",
        "This alert was sent automatically by the",
        "Intelligent Project Management System."
    ]

    return subject, "\n".join(lines)


def evaluate_project_risk(project, risk_status, data=None, force=False):
    """Records the latest risk status and emails the team when the project
    becomes at-risk. Returns a short outcome string (used by logs and tests)."""
    if project is None or not risk_status:
        return "no-status"

    try:
        previous = project["last_risk_status"] or ""
    except (KeyError, IndexError):
        previous = ""

    database.set_project_risk_status(project["id"], risk_status)

    if risk_status not in ALERT_LEVELS:
        return "below-alert-level"

    if not emailer.is_configured():
        return "email-not-configured"

    last_alert = database.get_last_alert(project["id"])
    if last_alert and not force:
        try:
            since = datetime.now() - datetime.fromisoformat(last_alert["sent_at"])
        except ValueError:
            since = timedelta(days=999)

        # Hard floor: never email about the same project more than once an hour.
        if since < timedelta(hours=1):
            return "cooldown"

        # While the project STAYS at risk, wait out the full cooldown.
        if previous == risk_status and since < timedelta(hours=get_cooldown_hours()):
            return "cooldown"

    recipients = database.list_alert_recipients(project["id"])
    if not recipients:
        return "no-recipients"

    subject, body = build_alert_email(project, risk_status, data)
    error = emailer.send_email(recipients, subject, body)
    if error:
        return f"send-failed: {error}"

    database.record_alert(project["id"], risk_status, ", ".join(recipients))
    return "sent"
