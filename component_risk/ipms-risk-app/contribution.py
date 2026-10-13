import os
import re
from collections import defaultdict

import requests

GITHUB_API = "https://api.github.com"

# Weighted scoring model for the Contribution Index (CI).
# Components follow the proposal: commit frequency, task completion,
# code quality, issue resolution and collaboration indicators.
WEIGHTS = {
    "commit_activity": 0.30,
    "task_completion": 0.25,
    "code_quality": 0.10,
    "issue_resolution": 0.15,
    "collaboration": 0.20
}

COMPONENT_LABELS = {
    "commit_activity": "Commit Activity",
    "task_completion": "Task Completion",
    "code_quality": "Code Quality",
    "issue_resolution": "Issue Resolution",
    "collaboration": "Collaboration"
}


def build_headers():
    headers = {"Accept": "application/vnd.github+json"}

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def extract_owner_repo(github_url):
    match = re.search(r"github\.com/([^/]+)/([^/]+)", github_url)

    if not match:
        return None, None

    return match.group(1), match.group(2).replace(".git", "")


def fetch_all_pages(url, headers, params=None, warnings=None):
    items = []
    page = 1

    while True:
        page_params = dict(params or {})
        page_params.update({"per_page": 100, "page": page})

        try:
            response = requests.get(url, headers=headers, params=page_params, timeout=15)
        except requests.RequestException:
            if warnings is not None:
                warnings.append(f"Network error while fetching {url.split('/repos/')[-1]}.")
            break

        if response.status_code == 403 and "rate limit" in response.text.lower():
            if warnings is not None:
                warnings.append(
                    "GitHub API rate limit reached. Set a GITHUB_TOKEN environment "
                    "variable to increase the limit; results may be incomplete."
                )
            break

        if response.status_code != 200:
            if warnings is not None:
                warnings.append(
                    f"GitHub returned status {response.status_code} for "
                    f"{url.split('/repos/')[-1]}."
                )
            break

        page_items = response.json()
        if not isinstance(page_items, list):
            break

        items.extend(page_items)

        if "next" not in response.links:
            break

        page += 1

    return items


KNOWN_BOT_ACCOUNTS = {
    "dependabot",
    "coveralls",
    "codecov",
    "github-actions",
    "renovate",
    "pre-commit-ci",
    "snyk-bot"
}


def is_bot(login):
    return login.endswith("[bot]") or login.lower() in KNOWN_BOT_ACCOUNTS


def new_member_stats():
    return {
        "commits": 0,
        "prs_opened": 0,
        "prs_merged": 0,
        "issues_opened": 0,
        "issues_resolved": 0,
        "comments": 0
    }


def collect_member_stats(owner, repo):
    headers = build_headers()
    warnings = []
    stats = defaultdict(new_member_stats)

    repo_base = f"{GITHUB_API}/repos/{owner}/{repo}"

    contributors = fetch_all_pages(f"{repo_base}/contributors", headers, warnings=warnings)
    for contributor in contributors:
        login = contributor.get("login")
        if login and not is_bot(login):
            stats[login]["commits"] += contributor.get("contributions", 0)

    pulls = fetch_all_pages(
        f"{repo_base}/pulls",
        headers,
        params={"state": "all"},
        warnings=warnings
    )
    for pull in pulls:
        login = (pull.get("user") or {}).get("login")
        if not login or is_bot(login):
            continue

        stats[login]["prs_opened"] += 1
        if pull.get("merged_at"):
            stats[login]["prs_merged"] += 1

    issues = fetch_all_pages(
        f"{repo_base}/issues",
        headers,
        params={"state": "all"},
        warnings=warnings
    )
    for issue in issues:
        # The issues endpoint also returns pull requests; skip them here.
        if "pull_request" in issue:
            continue

        author = (issue.get("user") or {}).get("login")
        if author and not is_bot(author):
            stats[author]["issues_opened"] += 1

        if issue.get("state") == "closed":
            assignees = [
                (assignee or {}).get("login")
                for assignee in issue.get("assignees") or []
            ]
            resolvers = [login for login in assignees if login and not is_bot(login)]

            # Credit assignees when present, otherwise fall back to the author.
            if not resolvers and author and not is_bot(author):
                resolvers = [author]

            for login in resolvers:
                stats[login]["issues_resolved"] += 1

    issue_comments = fetch_all_pages(f"{repo_base}/issues/comments", headers, warnings=warnings)
    review_comments = fetch_all_pages(f"{repo_base}/pulls/comments", headers, warnings=warnings)

    for comment in issue_comments + review_comments:
        login = (comment.get("user") or {}).get("login")
        if login and not is_bot(login):
            stats[login]["comments"] += 1

    return dict(stats), warnings


def relative_score(value, max_value):
    if max_value <= 0:
        return 0.0
    return round(value / max_value * 100, 1)


def component_raw_values(member):
    collaboration = member["comments"] + member["issues_opened"]

    return {
        "commit_activity": member["commits"],
        "task_completion": member["prs_merged"],
        "issue_resolution": member["issues_resolved"],
        "collaboration": collaboration
    }


def compute_contribution_index(github_url):
    owner, repo = extract_owner_repo(github_url)

    if owner is None or repo is None:
        return {"error": "Invalid GitHub repository URL.", "members": [], "warnings": []}

    stats, warnings = collect_member_stats(owner, repo)

    if not stats:
        return {
            "error": "No contributor activity found for this repository.",
            "members": [],
            "warnings": list(dict.fromkeys(warnings))
        }

    # Team-wide maximums used to score each member relative to the
    # most active member for that component.
    max_values = {
        component: max(
            component_raw_values(member)[component] for member in stats.values()
        )
        for component in ["commit_activity", "task_completion", "issue_resolution", "collaboration"]
    }
    any_prs_opened = any(member["prs_opened"] > 0 for member in stats.values())

    # A component only participates in the CI when the team produced
    # data for it (e.g. teams that never open PRs skip PR components),
    # and the remaining weights are renormalized.
    available = {
        "commit_activity": max_values["commit_activity"] > 0,
        "task_completion": max_values["task_completion"] > 0,
        "code_quality": any_prs_opened,
        "issue_resolution": max_values["issue_resolution"] > 0,
        "collaboration": max_values["collaboration"] > 0
    }
    active_weights = {
        component: weight
        for component, weight in WEIGHTS.items()
        if available[component]
    }
    total_weight = sum(active_weights.values())

    members = []
    for login, member in stats.items():
        raw = component_raw_values(member)

        scores = {
            "commit_activity": relative_score(raw["commit_activity"], max_values["commit_activity"]),
            "task_completion": relative_score(raw["task_completion"], max_values["task_completion"]),
            "issue_resolution": relative_score(raw["issue_resolution"], max_values["issue_resolution"]),
            "collaboration": relative_score(raw["collaboration"], max_values["collaboration"]),
            "code_quality": (
                round(member["prs_merged"] / member["prs_opened"] * 100, 1)
                if member["prs_opened"] > 0
                else 0.0
            )
        }

        ci = 0.0
        if total_weight > 0:
            ci = round(
                sum(scores[c] * w for c, w in active_weights.items()) / total_weight,
                1
            )

        members.append({
            "login": login,
            "stats": member,
            "scores": scores,
            "ci": ci
        })

    members.sort(key=lambda item: item["ci"], reverse=True)

    total_ci = sum(member["ci"] for member in members)
    for member in members:
        member["share"] = (
            round(member["ci"] / total_ci * 100, 1) if total_ci > 0 else 0.0
        )

    team = {
        "member_count": len(members),
        "average_ci": round(total_ci / len(members), 1),
        "total_commits": sum(m["stats"]["commits"] for m in members),
        "total_prs_merged": sum(m["stats"]["prs_merged"] for m in members),
        "total_issues_resolved": sum(m["stats"]["issues_resolved"] for m in members),
        "total_comments": sum(m["stats"]["comments"] for m in members)
    }

    skipped_components = [
        COMPONENT_LABELS[component]
        for component, is_available in available.items()
        if not is_available
    ]
    if skipped_components:
        warnings.append(
            "No team activity found for: "
            + ", ".join(skipped_components)
            + ". These components were excluded and the remaining weights renormalized."
        )

    return {
        "error": None,
        "repo": f"{owner}/{repo}",
        "members": members,
        "team": team,
        "weights": WEIGHTS,
        "component_labels": COMPONENT_LABELS,
        "warnings": list(dict.fromkeys(warnings))
    }
