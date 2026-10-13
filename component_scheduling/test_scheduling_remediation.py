"""Focused regression checks. Run only against an explicitly named test DB."""

from __future__ import annotations

import importlib
import hashlib
import hmac
import json
import os
import sys
import uuid
from datetime import date, timedelta
from io import BytesIO
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from PyPDF2 import PdfWriter


DATABASE_URL = os.environ.get("SCHEDULING_DATABASE_URL", "")
if urlsplit(DATABASE_URL).path.lstrip("/") != "ipms_scheduling_codex_test_20261010":
    pytest.skip(
        "Set SCHEDULING_DATABASE_URL to the isolated ipms_scheduling_codex_test_20261010 database",
        allow_module_level=True,
    )

sys.path.insert(0, os.path.dirname(__file__))
main = importlib.import_module("main")
auth = importlib.import_module("auth")
integration_security = importlib.import_module("integration_security")
progress_tracking = importlib.import_module("progress_tracking")
client = TestClient(main.app)
STAFF = {"Authorization": f"Bearer {auth.issue_token(auth.AuthenticatedUser('staff1', 'Staff', 'staff'))}"}


def test_assignment_route_is_unique_and_requires_login():
    routes = [route for route in main.app.routes if getattr(route, "path", None) == "/api/progress/auto-assign"]
    assert len(routes) == 1
    response = client.post("/api/progress/auto-assign", json={"team_members": ["A"], "tasks": []})
    assert response.status_code == 401
    duplicate_members = client.post(
        "/api/progress/auto-assign",
        json={"project_id": "R26-IT-CODEX-998", "team_members": ["IT-1", "it-1"],
              "tasks": [{"task_id": 1, "task_name": "Implement feature", "effort_hours": 2}]},
        headers=STAFF,
    )
    assert duplicate_members.status_code == 422


def test_production_auth_disables_demo_defaults(monkeypatch):
    monkeypatch.setenv("IPMS_ENV", "production")
    monkeypatch.delenv("IPMS_AUTH_USERS_JSON", raising=False)
    monkeypatch.delenv("IPMS_AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="demo accounts"):
        auth._users()
    with pytest.raises(RuntimeError, match="IPMS_AUTH_SECRET"):
        auth._secret()
    monkeypatch.delenv("IPMS_SUBMISSION_INTEGRATION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="IPMS_SUBMISSION_INTEGRATION_KEY"):
        integration_security.submission_integration_key()
    response = client.get(
        "/api/integrations/projects/R26-IT-CODEX-998/document-tasks",
        params={"student_id": "IT-1"},
    )
    assert response.status_code == 503


def test_assignment_creates_balanced_history_and_rejects_stale_tasks():
    project = "R26-IT-CODEX-998"
    tasks = [
        {"task_id": 1, "task_name": "Literature Review", "effort_hours": 16},
        {"task_id": 2, "task_name": "Backend API development", "effort_hours": 24},
        {"task_id": 3, "task_name": "Database implementation", "effort_hours": 32},
    ]
    with main.get_db_connection() as conn:
        conn.execute("DELETE FROM task_assignments WHERE project_id=?", (project,))
        conn.execute("DELETE FROM schedule_versions WHERE project_id=?", (project,))
        conn.execute(
            "INSERT INTO schedule_versions(project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",
            (project, 1, json.dumps({"schedule": tasks}), "2026-10-10T00:00:00"),
        )

    request = {"project_id": project, "team_members": ["IT-1", "IT-2"], "tasks": tasks}
    stale = {**request, "tasks": [{**tasks[0], "effort_hours": 100}, *tasks[1:]]}
    response = client.post("/api/progress/auto-assign", json=stale, headers=STAFF)
    assert response.status_code == 409, response.text
    assert "Tasks have changed" in response.text
    response = client.post("/api/progress/auto-assign", json=request, headers=STAFF)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["schedule_version"] == 2
    assert result["assign_method"] == "LPT Greedy (default)"
    assert len(result["schedule"]) == len(tasks)
    assert all(task["assignment_stage"] == "BALANCED" for task in result["schedule"])
    assert result["collaborative_count"] == 1
    assert result["parallel_count"] == 1

    with main.get_db_connection() as conn:
        versions = conn.execute(
            "SELECT version, schedule_json, team_members_json FROM schedule_versions WHERE project_id=? ORDER BY version", (project,)
        ).fetchall()
        assignment_count = conn.execute(
            "SELECT COUNT(*) FROM task_assignments WHERE project_id=?", (project,)
        ).fetchone()[0]
    assert [row[0] for row in versions] == [1, 2]
    assert "assignment_stage" not in versions[0][1]
    assert "BALANCED" in versions[1][1]
    assert json.loads(versions[1][2]) == ["IT-1", "IT-2"]
    assert assignment_count == 6  # shared source + copies, parallel copies, one role task

    repeat = client.post("/api/progress/auto-assign", json=request, headers=STAFF)
    assert repeat.status_code == 409, repeat.text
    assert "already balanced" in repeat.text

    with main.get_db_connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM schedule_versions WHERE project_id=?", (project,)
        ).fetchone()[0] == 2


def test_new_unassigned_schedule_history_restores_exact_member_ids():
    project = "CODEX-HISTORY-20261010"
    members = ["IT22101624", "IT22109576"]
    with main.get_db_connection() as conn:
        conn.execute("DELETE FROM schedule_versions WHERE project_id=?", (project,))
    response = client.post(
        "/api/schedule/generate",
        json={
            "project_id": project,
            "description": (
                "Research Topic: Scheduling test\n"
                "Team: IT22101624, IT22109576\n"
                "WORK BREAKDOWN STRUCTURE\n"
                "1. Literature Review\n2. System Design\n"
                "3. Backend Implementation\n4. Final Evaluation\n"
            ),
            "start_date": "2026-11-02", "team_size": 2,
            "duration_months": 2, "function_points": 50,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["team_members"] == members
    with main.get_db_connection() as conn:
        saved = conn.execute(
            "SELECT team_members_json FROM schedule_versions WHERE project_id=? ORDER BY id DESC LIMIT 1",
            (project,),
        ).fetchone()
    assert json.loads(saved[0]) == members
    history = client.get("/api/schedule/history", params={"group_id": project})
    assert history.status_code == 200, history.text
    item = history.json()["history"][0]
    assert item["team_members"] == members
    assert item["team_size"] == 2


def test_legacy_unassigned_history_does_not_invent_member_ids():
    project = "CODEX-LEGACY-HISTORY-20261010"
    task = {"task_id": 1, "task_name": "Design", "effort_hours": 4,
            "assigned_to": "UNASSIGNED", "start_date": "2026-11-02", "end_date": "2026-11-03"}
    with main.get_db_connection() as conn:
        conn.execute("DELETE FROM schedule_versions WHERE project_id=?", (project,))
        conn.execute(
            "INSERT INTO schedule_versions(project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",
            (project, 1, json.dumps([task]), "2026-10-10T00:00:00"),
        )
    item = client.get("/api/schedule/history", params={"group_id": project}).json()["history"][0]
    assert item["team_members"] == []
    assert item["team_size"] == 0


def test_history_list_survives_a_malformed_legacy_task():
    project = "CODEX-MALFORMED-HISTORY-20261010"
    with main.get_db_connection() as conn:
        conn.execute("DELETE FROM schedule_versions WHERE project_id=?", (project,))
        conn.execute(
            "INSERT INTO schedule_versions(project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",
            (project, 1, json.dumps({"schedule": ["bad task"]}), "2026-10-10T00:00:00"),
        )
    response = client.get("/api/schedule/history")
    assert response.status_code == 200, response.text
    item = next(item for item in response.json()["history"] if item["project_id"] == project)
    assert item["schedule"] == []


def test_deadline_checker_handles_legacy_wrappers_and_malformed_rows():
    prefix = "CODEX-DEADLINE-20261010"
    malformed, flat, wrapped = (f"{prefix}-A", f"{prefix}-B", f"{prefix}-C")
    today = date.today()
    soon = (today + timedelta(days=2)).isoformat()
    overdue = (today - timedelta(days=1)).isoformat()
    with main.get_db_connection() as conn:
        for project in (malformed, flat, wrapped):
            conn.execute("DELETE FROM notifications WHERE project_id=?", (project,))
            conn.execute("DELETE FROM schedule_versions WHERE project_id=?", (project,))
        for project, payload in (
            (malformed, '{invalid json'),
            (flat, json.dumps([{"task_id": 1, "task_name": "Flat task", "end_date": soon}])),
            (wrapped, json.dumps({"schedule": [
                {"task_id": 2, "task_name": "Wrapped task", "end_date": overdue},
                {"task_id": 3, "task_name": "Complete", "end_date": overdue, "status": "COMPLETED"},
                "bad task",
            ]})),
        ):
            conn.execute(
                "INSERT INTO schedule_versions(project_id, version, schedule_json, created_at) VALUES (?,?,?,?)",
                (project, 1, payload, "2026-10-10T00:00:00"),
            )
    main.check_deadlines()
    main.check_deadlines()  # unread notices must not duplicate
    with main.get_db_connection() as conn:
        notices = conn.execute(
            "SELECT project_id, task_id, type FROM notifications WHERE project_id IN (?,?,?) ORDER BY project_id",
            (malformed, flat, wrapped),
        ).fetchall()
    assert notices == [(flat, 1, "WARNING"), (wrapped, 2, "OVERDUE")]


def test_local_document_review_and_signed_github_evidence_flow(monkeypatch, tmp_path):
    """Synthetic signed delivery only: no GitHub or actual student account involved."""
    project = "CODEX-FLOW-20261010"
    student = "IT22117014"
    repo = "codex-example/ipms-handoff-flow-20261010"
    key = "local-test-integration-key"
    secret = "local-test-github-secret"
    monkeypatch.setenv("IPMS_SUBMISSION_INTEGRATION_KEY", key)
    monkeypatch.setenv("IPMS_GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(progress_tracking, "SUBMISSION_ROOT", tmp_path)
    tasks = [
        {"task_id": 1, "task_name": "Proposal report", "task_type": "DOCUMENT",
         "requires_document": True, "assigned_to": student},
        {"task_id": 2, "task_name": "Backend implementation", "task_type": "CODE",
         "requires_document": False, "assigned_to": student},
    ]
    with main.get_db_connection() as conn:
        for table in ("task_submissions", "task_progress", "progress_events", "notifications",
                      "github_commits", "student_github_identities", "github_registrations",
                      "task_assignments", "schedule_versions"):
            conn.execute(f"DELETE FROM {table} WHERE project_id=?", (project,))
        conn.execute(
            "INSERT INTO schedule_versions(project_id,version,schedule_json,created_at,team_members_json) VALUES (?,?,?,?,?)",
            (project, 1, json.dumps(tasks), "2026-10-10T00:00:00", json.dumps([student])),
        )
        for task in tasks:
            conn.execute(
                """INSERT INTO task_assignments
                   (project_id,task_id,task_name,assigned_to,effort_hours,status,assigned_at)
                   VALUES (?,?,?,?,?,'NOT_STARTED',?)""",
                (project, task["task_id"], task["task_name"], student, 8, "2026-10-10T00:00:00"),
            )

    listed = client.get(
        f"/api/integrations/projects/{project}/document-tasks",
        params={"student_id": student}, headers={"X-IPMS-Integration-Key": key},
    )
    assert listed.status_code == 200, listed.text
    assert [task["task_id"] for task in listed.json()["tasks"]] == [1]

    pdf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(pdf)
    uploaded = client.post(
        "/api/integrations/document-submissions",
        data={"project_id": project, "task_id": "1", "student_id": student},
        files={"file": ("proposal-evidence.pdf", pdf.getvalue(), "application/pdf")},
        headers={"X-IPMS-Integration-Key": key},
    )
    assert uploaded.status_code == 200, uploaded.text
    submission_id = uploaded.json()["submission_id"]
    assert uploaded.json()["status"] == "PENDING_REVIEW"
    queue = client.get("/api/progress/review-queue", params={"project_id": project}, headers=STAFF)
    assert queue.status_code == 200, queue.text
    assert any(item["submission_id"] == submission_id for item in queue.json().get("items", []))
    preview = client.get(f"/api/progress/submissions/{submission_id}/document", headers=STAFF)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF-")
    reviewed = client.post(
        f"/api/progress/submissions/{submission_id}/review",
        json={"decision": "APPROVED", "comments": "Local integration test"}, headers=STAFF,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["progress_percentage"] == 100

    registered = client.post(
        "/api/github/register",
        json={"project_id": project, "repo_url": f"https://github.com/{repo}"}, headers=STAFF,
    )
    assert registered.status_code == 200, registered.text
    identity = client.post(
        "/api/github/identities",
        json={"project_id": project, "student_id": student, "github_login": "codex-student"},
        headers=STAFF,
    )
    assert identity.status_code == 200, identity.text
    payload = {
        "ref": "refs/heads/main", "repository": {"full_name": repo},
        "commits": [{"id": uuid.uuid4().hex + uuid.uuid4().hex[:8],
                     "message": f"[{project}-TASK-002] Backend implementation",
                     "timestamp": "2026-10-10T12:00:00Z",
                     "author": {"username": "codex-student", "email": "student@example.test"}}],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    delivery = str(uuid.uuid4())
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    pushed = client.post(
        "/api/webhooks/github", content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature,
                 "X-GitHub-Delivery": delivery, "X-GitHub-Event": "push"},
    )
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()["linked"] == 1
    doc = client.get("/api/progress/tasks/1/evidence", params={"project_id": project}, headers=STAFF)
    code = client.get("/api/progress/tasks/2/evidence", params={"project_id": project}, headers=STAFF)
    assert doc.status_code == 200 and code.status_code == 200
    assert doc.json()["progress"]["status"] == "COMPLETED"
    assert doc.json()["submissions"][0]["review_status"] == "APPROVED"
    assert code.json()["progress"]["percentage"] == 10
    assert code.json()["github_commits"][0]["status"] == "LINKED"


def test_academic_hall_capacity_policy():
    assert main._academic_required_seats(4, 2) == 10
    assert not main._hall_has_capacity(9, 10)
    assert main._hall_has_capacity(10, 10)
    assert not main._hall_has_capacity(None, 10)
    with pytest.raises(ValueError):
        main._academic_required_seats(0, 0)


def test_academic_api_rejects_invalid_seating_policy():
    response = client.post(
        "/api/academic/auto-schedule",
        json={"start_date": "2026-11-02", "default_team_size": 0},
        headers=STAFF,
    )
    assert response.status_code == 422, response.text
    response = client.post(
        "/api/academic/auto-schedule",
        json={
            "start_date": "2026-11-02", "default_team_size": 4,
            "groups": [{"group_id": "R26-IT-CODEX-998", "topic": "software", "team_size": 0}],
        }, headers=STAFF,
    )
    assert response.status_code == 422, response.text


def test_academic_auto_schedule_reschedule_and_publish_check_capacity():
    with main.get_db_connection() as conn:
        conn.execute("DELETE FROM supervisors WHERE name LIKE ?", ("Codex Panel %",))
        conn.execute("DELETE FROM halls WHERE hall_name LIKE ?", ("Codex % Hall",))
        for name, role in (
            ("Codex Panel Prof", "Professor"), ("Codex Panel Doctor", "Doctor"),
            ("Codex Panel Lecturer", "Lecturer"), ("Codex Panel Instructor", "Instructor"),
        ):
            conn.execute(
                """INSERT INTO supervisors(name,email,expertise,available_dates,available_times,role,active)
                   VALUES (?,?,?,?,?,?,TRUE)""",
                (name, name.replace(" ", ".") + "@example.test", "software engineering", "", "09:00-17:00", role),
            )
        for name, capacity in (("Codex Small Hall", 7), ("Codex Large Hall", 10)):
            conn.execute(
                """INSERT INTO halls(hall_name,capacity,available_dates,available_times,active)
                   VALUES (?,?,'','09:00-17:00',TRUE)""", (name, capacity),
            )

    response = client.post(
        "/api/academic/auto-schedule",
        json={
            "start_date": "2026-11-02", "duration_minutes": 60,
            "proposal_week": 1, "pp1_week": 2, "pp2_week": 3, "viva_week": 4,
            "default_team_size": 4, "audience_seats": 2,
            "groups": [{"group_id": "R26-IT-CODEX-998", "topic": "software engineering"}],
        }, headers=STAFF,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["scheduled_count"] == 4
    assert {event["hall"] for event in result["schedule"]} == {"Codex Large Hall"}
    assert {event["required_seats"] for event in result["schedule"]} == {10}

    event = result["schedule"][0]
    response = client.post(
        f"/api/academic/events/{event['id']}/reschedule",
        json={"new_date": event["date"], "new_time": event["time"], "new_hall": "Codex Small Hall"},
        headers=STAFF,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "conflict"
    assert any(item["type"] == "hall_capacity" for item in response.json()["conflicts"])

    with main.get_db_connection() as conn:
        small_hall_id = conn.execute(
            "SELECT id FROM halls WHERE hall_name=?", ("Codex Small Hall",)
        ).fetchone()[0]
        large_hall_id = conn.execute(
            "SELECT id FROM halls WHERE hall_name=?", ("Codex Large Hall",)
        ).fetchone()[0]
        conn.execute(
            "UPDATE academic_events SET hall_id=?, hall_name=? WHERE id=?",
            (small_hall_id, "Codex Small Hall", event["id"]),
        )
    response = client.post(f"/api/academic/batches/{result['batch_id']}/publish", headers=STAFF)
    assert response.status_code == 409, response.text
    with main.get_db_connection() as conn:
        conn.execute(
            "UPDATE academic_events SET hall_id=?, hall_name=? WHERE id=?",
            (large_hall_id, "Codex Large Hall", event["id"]),
        )
    response = client.post(f"/api/academic/batches/{result['batch_id']}/publish", headers=STAFF)
    assert response.status_code == 200, response.text
