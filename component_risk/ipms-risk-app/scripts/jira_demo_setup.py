"""Create a Jira demo project with synthetic tasks mirroring a real GitHub repo."""
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

APP_DIR = r"C:\Projects 2026\INTELLIGENT PROJECT MANAGEMENT SYSTEM\ipms-risk-app"
load_dotenv(os.path.join(APP_DIR, ".env"))

BASE = os.environ["JIRA_BASE_URL"].rstrip("/")
AUTH = (os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
GITHUB_REPO = "agronholm/exceptiongroup"
PROJECT_KEY = "IPMS"
PROJECT_NAME = "IPMS Demo Project"

today = date.today()


def jira(method, path, **kwargs):
    r = requests.request(method, f"{BASE}{path}", auth=AUTH, timeout=30, **kwargs)
    return r


# ---- 1. Who am I ----------------------------------------------------------
me = jira("GET", "/rest/api/3/myself").json()
account_id = me["accountId"]
print(f"Jira user: {me.get('displayName')} ({account_id})")

# ---- 2. Get real issue titles from the GitHub repo ------------------------
gh = requests.get(
    f"https://api.github.com/repos/{GITHUB_REPO}/issues",
    headers={"Accept": "application/vnd.github+json"},
    params={"state": "all", "per_page": 20},
    timeout=15,
)
titles = []
if gh.status_code == 200:
    for item in gh.json():
        title = item.get("title", "").strip()
        if title and len(title) < 120:
            titles.append(title)
print(f"Fetched {len(titles)} real issue titles from {GITHUB_REPO}")

FALLBACK_TITLES = [
    "Set up project repository and CI pipeline",
    "Design database schema",
    "Implement user authentication",
    "Build dashboard UI components",
    "Write unit tests for API layer",
    "Fix pagination bug in issue list",
    "Add input validation to forms",
    "Optimize query performance",
    "Prepare progress presentation slides",
    "Integrate third-party API",
    "Refactor data processing module",
    "Update project documentation",
]
while len(titles) < 12:
    titles.append(FALLBACK_TITLES[len(titles) % len(FALLBACK_TITLES)])
titles = titles[:12]

# ---- 3. Create (or reuse) the demo project --------------------------------
existing = jira("GET", "/rest/api/3/project/search").json().get("values", [])
existing_keys = {p["key"] for p in existing}

if PROJECT_KEY in existing_keys:
    print(f"Project {PROJECT_KEY} already exists - reusing it.")
else:
    templates = [
        "com.pyxis.greenhopper.jira:gh-simplified-agility-kanban",
        "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic",
        "com.pyxis.greenhopper.jira:basic-software-development-template",
    ]
    created = False
    for template in templates:
        r = jira("POST", "/rest/api/3/project", json={
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "projectTypeKey": "software",
            "projectTemplateKey": template,
            "leadAccountId": account_id,
            "description": f"Synthetic demo data mirroring github.com/{GITHUB_REPO} for IPMS testing.",
        })
        if r.status_code in (200, 201):
            print(f"Created project {PROJECT_KEY} using template {template}")
            created = True
            break
        print(f"Template {template} failed ({r.status_code}): {r.text[:200]}")
    if not created:
        print("Could not create a new project; aborting.")
        sys.exit(1)

# ---- 4. Plan the synthetic tasks -------------------------------------------
# (title_index, target_status, due_offset_days, assign)
PLAN = [
    (0,  "Done",        +5,   True),   # done on time
    (1,  "Done",        +3,   True),   # done on time
    (2,  "Done",        0,    True),   # done on time (due today)
    (3,  "Done",        -7,   True),   # done LATE -> delay
    (4,  "Done",        -3,   True),   # done LATE -> delay
    (5,  "In Progress", -5,   True),   # OVERDUE
    (6,  "In Progress", -2,   True),   # OVERDUE
    (7,  "In Progress", +7,   True),   # on track
    (8,  "To Do",       -1,   True),   # OVERDUE
    (9,  "To Do",       +10,  True),
    (10, "To Do",       +14,  False),  # unassigned
    (11, "To Do",       None, False),  # unassigned, no due date
]

created_issues = []
for index, target_status, due_offset, assign in PLAN:
    fields = {
        "project": {"key": PROJECT_KEY},
        "summary": titles[index],
        "issuetype": {"name": "Task"},
    }
    if due_offset is not None:
        fields["duedate"] = (today + timedelta(days=due_offset)).strftime("%Y-%m-%d")
    if assign:
        fields["assignee"] = {"accountId": account_id}

    r = jira("POST", "/rest/api/3/issue", json={"fields": fields})
    if r.status_code not in (200, 201):
        print(f"  FAILED to create '{titles[index][:40]}': {r.status_code} {r.text[:200]}")
        continue
    key = r.json()["key"]
    created_issues.append((key, target_status))
    print(f"  created {key}: [{target_status}] due={fields.get('duedate', '-')} '{titles[index][:50]}'")

# ---- 5. Transition issues to their target status ---------------------------
for key, target_status in created_issues:
    if target_status == "To Do":
        continue
    transitions = jira("GET", f"/rest/api/3/issue/{key}/transitions").json().get("transitions", [])
    match = None
    for t in transitions:
        to = t.get("to", {})
        name = to.get("name", "").lower()
        category = (to.get("statusCategory") or {}).get("key")
        if target_status == "Done" and category == "done":
            match = t
            break
        if target_status == "In Progress" and category == "indeterminate":
            match = t
            break
    if not match:
        print(f"  {key}: no transition found to {target_status}")
        continue
    r = jira("POST", f"/rest/api/3/issue/{key}/transitions", json={"transition": {"id": match["id"]}})
    status = "ok" if r.status_code == 204 else f"FAILED {r.status_code}"
    print(f"  {key} -> {target_status}: {status}")

print()
print(f"Demo project ready: {BASE}/browse/{PROJECT_KEY}")
print(f"GitHub repo for the demo: https://github.com/{GITHUB_REPO}")
