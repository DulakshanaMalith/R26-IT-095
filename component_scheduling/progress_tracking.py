"""Verified progress evidence and supervisor review API.

Progress is deliberately stored outside ``schedule_versions``.  Schedule
versions describe the plan; these tables describe evidence against that plan.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import AuthenticatedUser, current_user, require_roles
from integration_security import submission_integration_key
from postgres_db import connect


router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
SUBMISSION_ROOT = BASE_DIR / "submissions"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",  # some browsers omit a useful Office MIME type
}
MAX_FILE_BYTES = int(os.getenv("IPMS_MAX_SUBMISSION_BYTES", str(20 * 1024 * 1024)))
TASK_REFERENCE_RE = re.compile(r"(?:\[|\b)(?:(?P<key>[A-Za-z0-9-]+-TASK-)(?P<number>\d+)|TASK[-_ ]?(?P<short>\d+))(?:\]|\b)", re.I)


class ReviewRequest(BaseModel):
    decision: str
    comments: str = ""


class ReviewerAssignmentRequest(BaseModel):
    project_id: str = Field(min_length=1)
    reviewer_username: str = Field(min_length=1)


class GithubRegistrationRequest(BaseModel):
    project_id: str = Field(min_length=1)
    repo_url: str = Field(min_length=1)


class GithubIdentityRequest(BaseModel):
    project_id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    github_login: str = Field(min_length=1)


class TaskAssignmentRequest(BaseModel):
    project_id: str = Field(min_length=1)
    task_id: int
    task_name: str
    assigned_to: str
    effort_hours: float = Field(ge=0)


class ManualCompletionRequest(BaseModel):
    project_id: str = Field(min_length=1)
    task_id: int
    reason: str = "Supervisor verified completion"


class VivaSnapshotRequest(BaseModel):
    event_id: int = Field(gt=0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task_key(project_id: str, task_id: int) -> str:
    return f"{project_id}-TASK-{int(task_id):03d}"


def _normalise_project_id(project_id: str) -> str:
    value = (project_id or "").strip()
    if not value or value.lower() == "demo_project_01":
        raise HTTPException(status_code=422, detail="A real Group ID is required.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,79}", value):
        raise HTTPException(status_code=422, detail="Group ID contains unsupported characters.")
    standard_group = re.fullmatch(r"(R\d{2}-[A-Za-z]+-)(\d{1,3})", value, re.I)
    if standard_group:
        value = f"{standard_group.group(1).upper()}{standard_group.group(2).zfill(3)}"
    return value


def _latest_schedule(connection, project_id: str) -> list[dict]:
    row = connection.execute(
        "SELECT schedule_json FROM schedule_versions WHERE project_id=? ORDER BY version DESC, id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No generated schedule exists for this Group ID.")
    try:
        schedule = json.loads(row[0])
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="The latest schedule record is invalid.") from exc
    if isinstance(schedule, dict):
        schedule = schedule.get("schedule", [])
    if not isinstance(schedule, list):
        raise HTTPException(status_code=500, detail="The latest schedule record is invalid.")
    return schedule


def _latest_task(connection, project_id: str, task_id: int) -> dict:
    schedule = _latest_schedule(connection, project_id)
    for task in schedule:
        if int(task.get("task_id", -1)) == int(task_id):
            return task
    raise HTTPException(status_code=404, detail="Task does not belong to this group's latest schedule.")


def _github_assignment_decision(task: dict, assigned_to: str | None,
                                student_id: str | None) -> tuple[str, str]:
    """Return evidence status and the authoritative task assignee.

    GitHub activity is useful evidence only when its mapped student owns the
    task, or when the task is explicitly collaborative/shared.  The GitHub
    identity never replaces the workload assignment.
    """
    authoritative = str(assigned_to or task.get("assigned_to") or "").strip()
    if not student_id:
        return "UNMAPPED_AUTHOR", authoritative
    is_shared = bool(task.get("is_collaborative") or task.get("is_parallel")) or bool(
        re.fullmatch(r"all(?:\s+members)?", authoritative, re.I)
    )
    if is_shared:
        return "LINKED", authoritative or "All Members"
    if not authoritative or authoritative.lower() == "unassigned":
        return "TASK_UNASSIGNED", authoritative
    assigned_members = {
        member.strip().lower() for member in authoritative.split(",") if member.strip()
    }
    if student_id.strip().lower() in assigned_members:
        return "LINKED", authoritative
    return "UNASSIGNED_AUTHOR", authoritative


def _task_schedule_state(*, start_date: str | None, end_date: str | None,
                         progress_percentage: float, status: str,
                         today: date | None = None) -> tuple[str, str | None]:
    """Classify live schedule health without flagging future work as late."""
    percentage = max(0.0, min(100.0, float(progress_percentage or 0)))
    if status in {"COMPLETED", "APPROVED"} or percentage >= 100:
        return "COMPLETED", None
    try:
        start = date.fromisoformat(str(start_date))
        end = date.fromisoformat(str(end_date))
    except (TypeError, ValueError):
        return "UNSCHEDULED", None
    current = today or _now().date()
    if current < start:
        return "EARLY_PROGRESS" if percentage > 0 else "UPCOMING", None
    if current > end:
        late_days = (current - end).days
        return "OVERDUE", f"Task is {late_days} day{'s' if late_days != 1 else ''} overdue"
    total_days = max(1, (end - start).days)
    elapsed_days = max(0, (current - start).days)
    expected = min(100.0, elapsed_days / total_days * 100.0)
    gap = expected - percentage
    if gap > 20:
        return "BEHIND", f"Task is {round(gap)}% behind its planned pace"
    return "ON_TRACK", None


def _tracking_plan_for_assignment(task_id: int, task_name: str | None,
                                  planned_by_id: dict[int, dict]) -> dict | None:
    """Map persisted assignment rows to current logical tracking units.

    A parallel source row in the Gantt is replaced by one ``[Component X]``
    assignment per member.  Shared-task per-member effort splits remain
    accounting rows and are not separate deliverables.
    """
    task_id = int(task_id)
    direct = planned_by_id.get(task_id)
    if direct is not None:
        return None if direct.get("is_parallel") else direct
    name = str(task_name or "")
    component_match = re.match(r"^\[Component [^\]]+\]\s*(.+)$", name, re.I)
    if not component_match:
        return None
    source_name = component_match.group(1).strip().casefold()
    return next((task for task in planned_by_id.values()
                 if task.get("is_parallel") and
                 str(task.get("task_name", "")).strip().casefold() == source_name), None)


def _can_review(connection, project_id: str, user: AuthenticatedUser) -> None:
    if user.role == "staff":
        return
    rows = connection.execute(
        "SELECT reviewer_username FROM project_reviewers WHERE project_id=?",
        (project_id,),
    ).fetchall()
    # Backward-compatible bootstrap: until staff assigns reviewers, authenticated
    # supervisors may review. Once mappings exist, they are enforced.
    if rows and user.username not in {row[0] for row in rows}:
        raise HTTPException(status_code=403, detail="You are not assigned to review this group.")


def _record_event(connection, *, project_id: str, task_id: int, event_type: str,
                  source: str, actor_id: str | None, evidence_id: str | None,
                  previous_progress: float, new_progress: float, metadata: dict | None = None) -> None:
    connection.execute(
        """INSERT INTO progress_events
           (project_id, task_id, task_key, event_type, source, actor_id, evidence_id,
            previous_progress, new_progress, metadata_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (project_id, task_id, _task_key(project_id, task_id), event_type, source,
         actor_id, evidence_id, previous_progress, new_progress,
         json.dumps(metadata or {}, separators=(",", ":"))),
    )


def _set_progress(connection, *, project_id: str, task_id: int, assigned_to: str | None,
                  status: str, percentage: float, source: str, actor: str) -> float:
    row = connection.execute(
        "SELECT progress_percentage FROM task_progress WHERE project_id=? AND task_id=?",
        (project_id, task_id),
    ).fetchone()
    previous = float(row[0]) if row else 0.0
    percentage = max(0.0, min(100.0, float(percentage)))
    connection.execute(
        """INSERT INTO task_progress
           (project_id, task_id, task_key, assigned_member_id, status, progress_percentage,
            progress_source, last_activity_at, updated_at, updated_by)
           VALUES (?,?,?,?,?,?,?,NOW(),NOW(),?)
           ON CONFLICT(project_id, task_id) DO UPDATE SET
             assigned_member_id=COALESCE(excluded.assigned_member_id, task_progress.assigned_member_id),
             status=excluded.status, progress_percentage=excluded.progress_percentage,
             progress_source=excluded.progress_source, last_activity_at=NOW(),
             updated_at=NOW(), updated_by=excluded.updated_by""",
        (project_id, task_id, _task_key(project_id, task_id), assigned_to, status,
         percentage, source, actor),
    )
    connection.execute(
        "UPDATE task_assignments SET status=? WHERE project_id=? AND task_id=?",
        (status, project_id, task_id),
    )
    return previous


@router.post("/api/progress/assign")
def assign_task(request: TaskAssignmentRequest,
                user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    project_id = _normalise_project_id(request.project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        _latest_task(connection, project_id, request.task_id)
        connection.execute(
            """INSERT INTO task_assignments
               (project_id, task_id, task_name, assigned_to, effort_hours, status, assigned_at)
               VALUES (?,?,?,?,?,'NOT_STARTED',?)
               ON CONFLICT(project_id, task_id) DO UPDATE SET
                 task_name=excluded.task_name, assigned_to=excluded.assigned_to,
                 effort_hours=excluded.effort_hours, assigned_at=excluded.assigned_at""",
            (project_id, request.task_id, request.task_name, request.assigned_to,
             request.effort_hours, _now().isoformat()),
        )
        existing = connection.execute(
            "SELECT progress_percentage, status FROM task_progress WHERE project_id=? AND task_id=?",
            (project_id, request.task_id),
        ).fetchone()
        _set_progress(
            connection, project_id=project_id, task_id=request.task_id,
            assigned_to=request.assigned_to, status=existing[1] if existing else "NOT_STARTED",
            percentage=float(existing[0]) if existing else 0, source="ASSIGNMENT", actor=user.username,
        )
        connection.commit()
        return {"status": "assigned", "task_id": request.task_id,
                "assigned_to": request.assigned_to}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.post("/api/progress/task-complete")
def manually_complete_task(request: ManualCompletionRequest,
                           user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    project_id = _normalise_project_id(request.project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        task = _latest_task(connection, project_id, request.task_id)
        assignment = connection.execute(
            "SELECT assigned_to FROM task_assignments WHERE project_id=? AND task_id=?",
            (project_id, request.task_id),
        ).fetchone()
        previous = _set_progress(
            connection, project_id=project_id, task_id=request.task_id,
            assigned_to=assignment[0] if assignment else task.get("assigned_to"),
            status="COMPLETED", percentage=100, source="MANUAL_REVIEW", actor=user.username,
        )
        _record_event(
            connection, project_id=project_id, task_id=request.task_id,
            event_type="MANUAL_PROGRESS_COMPLETED", source="MANUAL_REVIEW",
            actor_id=user.username, evidence_id=None, previous_progress=previous,
            new_progress=100, metadata={"reason": request.reason.strip()},
        )
        connection.commit()
        return {"status": "completed", "task_id": request.task_id,
                "progress_percentage": 100, "verified_by": user.display}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/api/progress/individual")
def individual_progress(project_id: str,
                        user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    """Return effort-weighted verified progress, including partial evidence."""
    project_id = _normalise_project_id(project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        schedule_by_id = {
            int(task.get("task_id")): task for task in _latest_schedule(connection, project_id)
            if task.get("task_id") is not None
        }
        rows = connection.execute(
            """SELECT ta.assigned_to, ta.task_id, ta.task_name, ta.effort_hours,
                      COALESCE(tp.status, ta.status, 'NOT_STARTED'),
                      COALESCE(tp.progress_percentage,
                        CASE WHEN ta.status='COMPLETED' THEN 100 ELSE 0 END),
                      COALESCE(tp.progress_source, 'ASSIGNMENT')
               FROM task_assignments ta
               LEFT JOIN task_progress tp
                 ON tp.project_id=ta.project_id AND tp.task_id=ta.task_id
               WHERE ta.project_id=? ORDER BY ta.task_id""", (project_id,),
        ).fetchall()
        members: dict[str, dict] = {}
        for member, task_id, task_name, effort, status, percentage, source in rows:
            planned_task = _tracking_plan_for_assignment(task_id, task_name, schedule_by_id)
            if planned_task is None:
                continue
            member = member or "Unassigned"
            effort = float(effort or 0)
            percentage = max(0.0, min(100.0, float(percentage or 0)))
            schedule_state, schedule_reason = _task_schedule_state(
                start_date=planned_task.get("start_date"), end_date=planned_task.get("end_date"),
                progress_percentage=percentage, status=str(status or "NOT_STARTED"),
            )
            bucket = members.setdefault(member, {"tasks": [], "total_effort": 0.0,
                                                  "verified_effort": 0.0})
            bucket["tasks"].append({"task_id": task_id, "task_name": task_name,
                                    "effort_hours": effort, "status": status,
                                    "progress_pct": round(percentage, 1), "progress_source": source,
                                    "start_date": planned_task.get("start_date"),
                                    "end_date": planned_task.get("end_date"),
                                    "schedule_state": schedule_state,
                                    "schedule_reason": schedule_reason})
            bucket["total_effort"] += effort
            bucket["verified_effort"] += effort * percentage / 100.0
        result = []
        for member, bucket in members.items():
            total = bucket["total_effort"]
            verified = bucket["verified_effort"]
            percentage = round(verified / total * 100, 1) if total else 0.0
            completed_count = sum(
                1 for task in bucket["tasks"]
                if task["status"] in {"COMPLETED", "APPROVED"} or task["progress_pct"] >= 100
            )
            bottleneck_tasks = [
                task for task in bucket["tasks"] if task["schedule_state"] in {"BEHIND", "OVERDUE"}
            ]
            result.append({"member": member, "total_tasks": len(bucket["tasks"]),
                           "completed_tasks": completed_count,
                           "total_effort_hours": round(total, 1),
                           "completed_effort_hours": round(verified, 1),
                           "progress_pct": percentage,
                           "is_bottleneck": bool(bottleneck_tasks),
                           "bottleneck_reason": bottleneck_tasks[0]["schedule_reason"] if bottleneck_tasks else None,
                           "bottleneck_task_count": len(bottleneck_tasks),
                           "tasks": bucket["tasks"]})
        total_effort = sum(item["total_effort_hours"] for item in result)
        verified_effort = sum(item["completed_effort_hours"] for item in result)
        project_percentage = round(verified_effort / total_effort * 100, 1) if total_effort else 0.0
        return {"members": sorted(result, key=lambda item: item["progress_pct"], reverse=True),
                "project_progress_pct": project_percentage,
                "total_effort_hours": round(total_effort, 1),
                "completed_effort_hours": round(verified_effort, 1)}
    finally:
        connection.close()


def _build_viva_progress_summary(connection, project_id: str) -> dict:
    """Build a read-only, evidence-backed project summary for a Viva panel."""
    try:
        planned_tasks = _latest_schedule(connection, project_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {"available": False, "project_id": project_id,
                    "message": "No generated project schedule is available."}
        raise
    planned_by_id = {
        int(task["task_id"]): task for task in planned_tasks if task.get("task_id") is not None
    }
    rows = connection.execute(
        """SELECT ta.task_id, ta.task_name, ta.effort_hours,
                  COALESCE(tp.status, ta.status, 'NOT_STARTED'),
                  COALESCE(tp.progress_percentage,
                    CASE WHEN ta.status='COMPLETED' THEN 100 ELSE 0 END)
           FROM task_assignments ta
           LEFT JOIN task_progress tp
             ON tp.project_id=ta.project_id AND tp.task_id=ta.task_id
           WHERE ta.project_id=? ORDER BY ta.task_id""", (project_id,),
    ).fetchall()
    rows = [(row, _tracking_plan_for_assignment(row[0], row[1], planned_by_id)) for row in rows]
    rows = [(row, planned) for row, planned in rows if planned is not None]
    if not rows:
        return {"available": False, "project_id": project_id,
                "message": "The generated schedule has not been assigned and tracked yet."}
    total_effort = completed_effort = 0.0
    completed = in_progress = not_started = behind = overdue = 0
    for row, planned in rows:
        task_id, _task_name, effort, status, percentage = row
        effort = float(effort or 0)
        percentage = max(0.0, min(100.0, float(percentage or 0)))
        total_effort += effort
        completed_effort += effort * percentage / 100.0
        if status in {"COMPLETED", "APPROVED"} or percentage >= 100:
            completed += 1
        elif percentage > 0:
            in_progress += 1
        else:
            not_started += 1
        schedule_state, _ = _task_schedule_state(
            start_date=planned.get("start_date"), end_date=planned.get("end_date"),
            progress_percentage=percentage, status=str(status),
        )
        behind += int(schedule_state == "BEHIND")
        overdue += int(schedule_state == "OVERDUE")
    document_counts = connection.execute(
        """SELECT COUNT(*),
                  COUNT(*) FILTER (WHERE status='APPROVED'),
                  COUNT(*) FILTER (WHERE status IN ('SUBMITTED','PENDING_REVIEW'))
           FROM task_submissions WHERE project_id=?""", (project_id,),
    ).fetchone()
    git_counts = connection.execute(
        """SELECT COUNT(*),
                  COUNT(*) FILTER (WHERE evidence_status='LINKED'),
                  COUNT(*) FILTER (WHERE evidence_status<>'LINKED')
           FROM github_commits WHERE project_id=?""", (project_id,),
    ).fetchone()
    last_activity = connection.execute(
        "SELECT MAX(created_at) FROM progress_events WHERE project_id=?", (project_id,),
    ).fetchone()
    overall = round(completed_effort / total_effort * 100, 1) if total_effort else 0.0
    warnings = []
    if overdue:
        warnings.append(f"{overdue} task{'s are' if overdue != 1 else ' is'} overdue")
    if behind:
        warnings.append(f"{behind} task{'s are' if behind != 1 else ' is'} behind planned pace")
    if int(git_counts[2] or 0):
        warnings.append(f"{int(git_counts[2])} Git item{'s need' if int(git_counts[2]) != 1 else ' needs'} evidence review")
    return {
        "available": True, "project_id": project_id,
        "overall_progress_pct": overall, "total_tasks": len(rows),
        "completed_tasks": completed, "in_progress_tasks": in_progress,
        "not_started_tasks": not_started, "behind_tasks": behind,
        "overdue_tasks": overdue, "total_effort_hours": round(total_effort, 1),
        "verified_effort_hours": round(completed_effort, 1),
        "documents": {"total": int(document_counts[0] or 0),
                      "approved": int(document_counts[1] or 0),
                      "pending_review": int(document_counts[2] or 0)},
        "github": {"total": int(git_counts[0] or 0), "linked": int(git_counts[1] or 0),
                   "flagged": int(git_counts[2] or 0)},
        "last_activity_at": str(last_activity[0]) if last_activity and last_activity[0] else None,
        "warnings": warnings,
    }


def _viva_event_project(connection, event_id: int) -> str:
    row = connection.execute(
        "SELECT group_id, event_type FROM academic_events WHERE id=?", (event_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Academic event was not found.")
    if str(row[1]).lower() != "viva":
        raise HTTPException(status_code=422, detail="Progress snapshots are available only for Viva events.")
    return _normalise_project_id(row[0])


@router.get("/api/progress/viva-summary")
def viva_progress_summary(event_id: int,
                          user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    connection = connect()
    try:
        project_id = _viva_event_project(connection, event_id)
        _can_review(connection, project_id, user)
        frozen = connection.execute(
            "SELECT snapshot_json, captured_by, captured_at FROM viva_progress_snapshots WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if frozen:
            summary = json.loads(frozen[0])
            summary.update({"snapshot_mode": "FROZEN", "captured_by": frozen[1],
                            "captured_at": str(frozen[2])})
            return summary
        summary = _build_viva_progress_summary(connection, project_id)
        summary["snapshot_mode"] = "LIVE"
        return summary
    finally:
        connection.close()


@router.post("/api/progress/viva-snapshot")
def freeze_viva_progress(request: VivaSnapshotRequest,
                         user: AuthenticatedUser = Depends(require_roles("staff"))):
    connection = connect()
    try:
        project_id = _viva_event_project(connection, request.event_id)
        summary = _build_viva_progress_summary(connection, project_id)
        if not summary.get("available"):
            raise HTTPException(status_code=409, detail=summary.get("message"))
        connection.execute(
            """INSERT INTO viva_progress_snapshots
               (event_id, project_id, snapshot_json, captured_by)
               VALUES (?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET
               project_id=excluded.project_id, snapshot_json=excluded.snapshot_json,
               captured_by=excluded.captured_by, captured_at=NOW()""",
            (request.event_id, project_id, json.dumps(summary), user.username),
        )
        connection.commit()
        summary.update({"snapshot_mode": "FROZEN", "captured_by": user.username})
        return summary
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/api/progress/overview")
def progress_overview(project_id: str,
                      user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    """Small task map used to hydrate Gantt bars without one request per task."""
    project_id = _normalise_project_id(project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        rows = connection.execute(
            """SELECT tp.task_id, tp.task_key, tp.status, tp.progress_percentage,
                      tp.progress_source, tp.last_activity_at,
                      COUNT(DISTINCT ts.id), COUNT(DISTINCT gc.id), COUNT(DISTINCT gp.id)
               FROM task_progress tp
               LEFT JOIN task_submissions ts
                 ON ts.project_id=tp.project_id AND ts.task_id=tp.task_id
               LEFT JOIN github_commits gc
                 ON gc.project_id=tp.project_id AND gc.task_id=tp.task_id
               LEFT JOIN github_pull_requests gp
                 ON gp.project_id=tp.project_id AND gp.task_id=tp.task_id
               WHERE tp.project_id=?
               GROUP BY tp.task_id, tp.task_key, tp.status, tp.progress_percentage,
                        tp.progress_source, tp.last_activity_at""", (project_id,),
        ).fetchall()
        return {"project_id": project_id, "tasks": {
            str(row[0]): {"task_key": row[1], "status": row[2],
                          "progress_percentage": float(row[3] or 0), "source": row[4],
                          "last_activity_at": str(row[5]) if row[5] else None,
                          "document_count": int(row[6]), "commit_count": int(row[7]),
                          "pull_request_count": int(row[8])}
            for row in rows}}
    finally:
        connection.close()


async def _save_submission(*, project_id: str, task_id: int, student_id: str,
                           upload: UploadFile, is_test: bool, actor: str) -> dict:
    project_id = _normalise_project_id(project_id)
    original_name = Path(upload.filename or "submission").name
    extension = Path(original_name).suffix.lower()
    mime_type = (upload.content_type or "application/octet-stream").lower()
    if extension not in ALLOWED_EXTENSIONS or mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Only PDF, Word and plain-text documents are accepted.")
    content = await upload.read(MAX_FILE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The submitted document is empty.")
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"Document exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit.")
    signatures_valid = {
        ".pdf": content.startswith(b"%PDF-"),
        ".docx": content.startswith(b"PK\x03\x04"),
        ".doc": content.startswith(b"\xd0\xcf\x11\xe0"),
        ".txt": b"\x00" not in content[:4096],
    }
    if not signatures_valid.get(extension, False):
        raise HTTPException(status_code=415, detail="Document content does not match its file extension.")
    digest = hashlib.sha256(content).hexdigest()

    connection = connect()
    stored_path: Path | None = None
    try:
        task = _latest_task(connection, project_id, task_id)
        if str(task.get("task_type", "")).upper() == "CODE" and not task.get("requires_document"):
            raise HTTPException(status_code=422, detail="This code task is not configured to accept document evidence.")
        assignment = connection.execute(
            "SELECT assigned_to FROM task_assignments WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
        assigned_to = str((assignment[0] if assignment else task.get("assigned_to")) or "").strip()
        if assigned_to and not re.fullmatch(r"all(?:\s+members)?", assigned_to, re.I):
            assigned_members = {member.strip().lower() for member in assigned_to.split(",") if member.strip()}
            if student_id.strip().lower() not in assigned_members:
                raise HTTPException(status_code=403, detail="Student is not assigned to this task.")
        duplicate = connection.execute(
            "SELECT id FROM task_submissions WHERE project_id=? AND task_id=? AND sha256_hash=?",
            (project_id, task_id, digest),
        ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="This exact document has already been submitted for the task.")
        version_row = connection.execute(
            "SELECT COALESCE(MAX(submission_version),0)+1 FROM task_submissions WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
        version = int(version_row[0])
        storage_dir = SUBMISSION_ROOT / project_id / str(task_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"v{version}_{uuid.uuid4().hex}{extension}"
        stored_path = (storage_dir / stored_name).resolve()
        if storage_dir.resolve() not in stored_path.parents:
            raise HTTPException(status_code=400, detail="Unsafe document path.")
        stored_path.write_bytes(content)

        cursor = connection.execute(
            """INSERT INTO task_submissions
               (project_id, task_id, task_key, student_id, submission_version, filename,
                original_filename, stored_filename, storage_path, mime_type, file_size,
                sha256_hash, submitted_at, status, review_status, is_test)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'SUBMITTED','PENDING_REVIEW',?) RETURNING id""",
            (project_id, task_id, _task_key(project_id, task_id), student_id.strip(), version,
             original_name, original_name, stored_name, str(stored_path), mime_type,
             len(content), digest, _now().isoformat(), is_test),
        )
        submission_id = int(cursor.fetchone()[0])
        existing_progress = connection.execute(
            "SELECT progress_percentage FROM task_progress WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
        retained_progress = float(existing_progress[0]) if existing_progress else 0.0
        previous = _set_progress(
            connection, project_id=project_id, task_id=task_id, assigned_to=assigned_to,
            status="PENDING_REVIEW", percentage=retained_progress, source="DOCUMENT", actor=actor,
        )
        _record_event(
            connection, project_id=project_id, task_id=task_id,
            event_type="DOCUMENT_SUBMITTED", source="TEST" if is_test else "DOCUMENT",
            actor_id=actor, evidence_id=str(submission_id), previous_progress=previous,
            new_progress=retained_progress, metadata={"filename": original_name, "version": version,
                                     "student_id": student_id, "is_test": is_test},
        )
        connection.execute(
            """INSERT INTO notifications
               (project_id, task_id, task_name, type, message, created_at, is_read)
               VALUES (?,?,?,?,?,?,0)""",
            (project_id, task_id, task.get("task_name", _task_key(project_id, task_id)),
             "REVIEW", f"Document v{version} is waiting for supervisor review.", _now().isoformat()),
        )
        connection.commit()
        return {"status": "PENDING_REVIEW", "submission_id": submission_id,
                "task_id": task_id, "task_key": _task_key(project_id, task_id),
                "version": version, "filename": original_name, "is_test": is_test,
                "message": "Document submitted and queued for supervisor review."}
    except Exception:
        connection.rollback()
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise
    finally:
        connection.close()


@router.post("/api/integrations/document-submissions")
async def receive_component_submission(
    project_id: str = Form(...), task_id: int = Form(...), student_id: str = Form(...),
    file: UploadFile = File(...), x_ipms_integration_key: str | None = Header(default=None),
):
    if os.getenv("IPMS_ENV", "").strip().lower() == "production":
        raise HTTPException(status_code=503, detail="Test-only student submissions require verified student authentication before production use.")
    expected = submission_integration_key()
    if not x_ipms_integration_key or not hmac.compare_digest(expected, x_ipms_integration_key):
        raise HTTPException(status_code=401, detail="Invalid component integration key.")
    return await _save_submission(project_id=project_id, task_id=task_id,
                                  student_id=student_id, upload=file,
                                  is_test=False, actor=f"integration:{student_id}")


@router.get("/api/integrations/projects/{project_id}/document-tasks")
def integration_document_tasks(
    project_id: str, student_id: str,
    x_ipms_integration_key: str | None = Header(default=None),
):
    """Return document tasks assigned to a student for the standalone portal."""
    if os.getenv("IPMS_ENV", "").strip().lower() == "production":
        raise HTTPException(status_code=503, detail="Test-only student task access requires verified student authentication before production use.")
    expected = submission_integration_key()
    if not x_ipms_integration_key or not hmac.compare_digest(expected, x_ipms_integration_key):
        raise HTTPException(status_code=401, detail="Invalid component integration key.")
    project_id = _normalise_project_id(project_id)
    connection = connect()
    try:
        row = connection.execute(
            """SELECT schedule_json FROM schedule_versions WHERE project_id=?
               ORDER BY version DESC, id DESC LIMIT 1""", (project_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No generated schedule exists for this Group ID.")
        schedule = json.loads(row[0])
        if isinstance(schedule, dict):
            schedule = schedule.get("schedule", [])
        requested_student = student_id.strip().lower()
        tasks = []
        for task in schedule:
            if str(task.get("task_type", "")).upper() != "DOCUMENT" and not task.get("requires_document"):
                continue
            task_id = int(task.get("task_id"))
            assignment = connection.execute(
                "SELECT assigned_to FROM task_assignments WHERE project_id=? AND task_id=?",
                (project_id, task_id),
            ).fetchone()
            assigned_to = str((assignment[0] if assignment else task.get("assigned_to")) or "").strip()
            assigned_members = {item.strip().lower() for item in assigned_to.split(",") if item.strip()}
            is_shared = bool(task.get("is_collaborative") or task.get("is_parallel")) or bool(
                re.fullmatch(r"all(?:\s+members)?", assigned_to, re.I)
            )
            if assigned_members and not is_shared and requested_student not in assigned_members:
                continue
            progress = connection.execute(
                """SELECT status, progress_percentage FROM task_progress
                   WHERE project_id=? AND task_id=?""", (project_id, task_id),
            ).fetchone()
            tasks.append({
                "task_id": task_id,
                "task_key": task.get("task_key") or _task_key(project_id, task_id),
                "task_name": task.get("task_name", ""),
                "assigned_to": assigned_to,
                "end_date": task.get("end_date"),
                "status": progress[0] if progress else task.get("status", "NOT_STARTED"),
                "progress_percentage": float(progress[1]) if progress else float(task.get("progress_pct", 0)),
            })
        return {"project_id": project_id, "student_id": student_id.strip(), "tasks": tasks}
    finally:
        connection.close()


@router.get("/api/progress/submissions/{submission_id}/document")
def view_submission(submission_id: int, user: AuthenticatedUser = Depends(current_user)):
    connection = connect()
    try:
        row = connection.execute(
            """SELECT project_id, storage_path, original_filename, mime_type
               FROM task_submissions WHERE id=?""", (submission_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found.")
        _can_review(connection, row[0], user)
        path = Path(row[1] or "").resolve()
        if SUBMISSION_ROOT.resolve() not in path.parents or not path.is_file():
            raise HTTPException(status_code=404, detail="Stored document is unavailable.")
        disposition = "inline" if row[3] == "application/pdf" else "attachment"
        return FileResponse(path, media_type=row[3] or "application/octet-stream",
                            filename=row[2] or path.name,
                            content_disposition_type=disposition)
    finally:
        connection.close()


@router.post("/api/progress/submissions/{submission_id}/review")
def review_submission(submission_id: int, request: ReviewRequest,
                      user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    decision = request.decision.strip().upper()
    if decision not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED"}:
        raise HTTPException(status_code=422, detail="Decision must be APPROVED, REJECTED or CHANGES_REQUESTED.")
    if decision != "APPROVED" and not request.comments.strip():
        raise HTTPException(status_code=422, detail="Review comments are required for rejection or requested changes.")
    connection = connect()
    try:
        row = connection.execute(
            """SELECT project_id, task_id, review_status, student_id, original_filename
               FROM task_submissions WHERE id=? FOR UPDATE""", (submission_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found.")
        project_id, task_id, current_status, student_id, filename = row
        _can_review(connection, project_id, user)
        if current_status != "PENDING_REVIEW":
            raise HTTPException(status_code=409, detail=f"Submission has already been reviewed as {current_status}.")
        progress_row = connection.execute(
            "SELECT progress_percentage FROM task_progress WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
        current_progress = float(progress_row[0]) if progress_row else 0.0
        if decision == "APPROVED":
            task_status, percentage = "COMPLETED", 100.0
        elif decision == "CHANGES_REQUESTED":
            task_status, percentage = "CHANGES_REQUESTED", current_progress
        else:
            task_status, percentage = "REJECTED", current_progress
        connection.execute(
            """UPDATE task_submissions SET review_status=?, status=?, reviewer_id=?,
               review_comments=?, reviewed_at=NOW() WHERE id=?""",
            (decision, decision, user.username, request.comments.strip(), submission_id),
        )
        previous = _set_progress(
            connection, project_id=project_id, task_id=task_id, assigned_to=None,
            status=task_status, percentage=percentage, source="SUPERVISOR_REVIEW", actor=user.username,
        )
        _record_event(
            connection, project_id=project_id, task_id=task_id,
            event_type=f"DOCUMENT_{decision}", source="SUPERVISOR_REVIEW",
            actor_id=user.username, evidence_id=str(submission_id),
            previous_progress=previous, new_progress=percentage,
            metadata={"comments": request.comments.strip(), "filename": filename,
                      "student_id": student_id},
        )
        connection.execute(
            """INSERT INTO notifications
               (project_id, task_id, task_name, type, message, created_at, is_read)
               VALUES (?,?,?,?,?,?,0)""",
            (project_id, task_id, _task_key(project_id, task_id), "PROGRESS",
             f"Submission was {decision.lower().replace('_', ' ')} by {user.display}.",
             _now().isoformat()),
        )
        connection.commit()
        return {"status": decision, "submission_id": submission_id, "task_id": task_id,
                "progress_percentage": percentage, "reviewed_by": user.display}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.get("/api/progress/tasks/{task_id}/evidence")
def task_evidence(task_id: int, project_id: str,
                  user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    project_id = _normalise_project_id(project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        task = _latest_task(connection, project_id, task_id)
        progress = connection.execute(
            """SELECT status, progress_percentage, progress_source, last_activity_at
               FROM task_progress WHERE project_id=? AND task_id=?""",
            (project_id, task_id),
        ).fetchone()
        submissions = connection.execute(
            """SELECT id, student_id, submission_version, original_filename, mime_type,
                      file_size, submitted_at, review_status, reviewer_id, review_comments,
                      reviewed_at, is_test
               FROM task_submissions WHERE project_id=? AND task_id=?
               ORDER BY submission_version DESC, id DESC""",
            (project_id, task_id),
        ).fetchall()
        commits = connection.execute(
            """SELECT commit_sha, author_login, linked_student_id, message, branch,
                      evidence_status, committed_at
               FROM github_commits WHERE project_id=? AND task_id=? ORDER BY id DESC LIMIT 100""",
            (project_id, task_id),
        ).fetchall()
        pull_requests = connection.execute(
            """SELECT pull_number, author_login, linked_student_id, title, branch,
                      html_url, state, review_status, merged, updated_at, evidence_status
               FROM github_pull_requests WHERE project_id=? AND task_id=?
               ORDER BY pull_number DESC LIMIT 100""", (project_id, task_id),
        ).fetchall()
        events = connection.execute(
            """SELECT event_type, source, actor_id, evidence_id, previous_progress,
                      new_progress, metadata_json, created_at
               FROM progress_events WHERE project_id=? AND task_id=? ORDER BY id DESC LIMIT 100""",
            (project_id, task_id),
        ).fetchall()
        return {
            "project_id": project_id, "task_id": task_id,
            "task_key": _task_key(project_id, task_id), "task_name": task.get("task_name", ""),
            "progress": {"status": progress[0], "percentage": progress[1],
                         "source": progress[2], "last_activity_at": str(progress[3])}
                        if progress else {"status": task.get("status", "NOT_STARTED"),
                                          "percentage": task.get("progress_pct", 0), "source": "SCHEDULE"},
            "submissions": [
                {"id": r[0], "student_id": r[1], "version": r[2], "filename": r[3],
                 "mime_type": r[4], "file_size": r[5], "submitted_at": r[6],
                 "review_status": r[7], "reviewer_id": r[8], "review_comments": r[9],
                 "reviewed_at": str(r[10]) if r[10] else None, "is_test": bool(r[11]),
                 "document_url": f"/api/progress/submissions/{r[0]}/document"}
                for r in submissions
            ],
            "github_commits": [
                {"sha": r[0], "author": r[1], "student_id": r[2], "message": r[3],
                 "branch": r[4], "status": r[5], "committed_at": r[6]} for r in commits
            ],
            "github_pull_requests": [
                {"number": r[0], "author": r[1], "student_id": r[2], "title": r[3],
                 "branch": r[4], "url": r[5], "state": r[6], "review_status": r[7],
                 "merged": bool(r[8]), "updated_at": r[9], "evidence_status": r[10]}
                for r in pull_requests
            ],
            "events": [
                {"event_type": r[0], "source": r[1], "actor_id": r[2],
                 "evidence_id": r[3], "previous_progress": r[4], "new_progress": r[5],
                 "metadata": json.loads(r[6] or "{}"), "created_at": str(r[7])} for r in events
            ],
        }
    finally:
        connection.close()


@router.get("/api/progress/review-queue")
def review_queue(project_id: str | None = None,
                 user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    connection = connect()
    try:
        params: list = []
        where = "WHERE ts.review_status='PENDING_REVIEW'"
        if project_id:
            project_id = _normalise_project_id(project_id)
            _can_review(connection, project_id, user)
            where += " AND ts.project_id=?"
            params.append(project_id)
        elif user.role == "supervisor":
            mapped = connection.execute(
                "SELECT project_id FROM project_reviewers WHERE reviewer_username=?", (user.username,),
            ).fetchall()
            if mapped:
                placeholders = ",".join("?" for _ in mapped)
                where += f" AND ts.project_id IN ({placeholders})"
                params.extend(row[0] for row in mapped)
        rows = connection.execute(
            f"""SELECT ts.id, ts.project_id, ts.task_id, ts.task_key, ta.task_name,
                       ts.student_id, ts.submission_version, ts.original_filename,
                       ts.submitted_at, ts.is_test
                FROM task_submissions ts
                LEFT JOIN task_assignments ta
                  ON ta.project_id=ts.project_id AND ta.task_id=ts.task_id
                {where} ORDER BY ts.submitted_at ASC""", params,
        ).fetchall()
        return {"items": [
            {"submission_id": r[0], "project_id": r[1], "task_id": r[2],
             "task_key": r[3], "task_name": r[4] or r[3], "student_id": r[5],
             "version": r[6], "filename": r[7], "submitted_at": r[8],
             "is_test": bool(r[9]),
             "document_url": f"/api/progress/submissions/{r[0]}/document"}
            for r in rows]}
    finally:
        connection.close()


@router.post("/api/progress/reviewers")
def assign_reviewer(request: ReviewerAssignmentRequest,
                    user: AuthenticatedUser = Depends(require_roles("staff"))):
    project_id = _normalise_project_id(request.project_id)
    connection = connect()
    try:
        connection.execute(
            """INSERT INTO project_reviewers(project_id, reviewer_username, assigned_by)
               VALUES (?,?,?) ON CONFLICT(project_id, reviewer_username) DO NOTHING""",
            (project_id, request.reviewer_username.strip(), user.username),
        )
        connection.commit()
        return {"status": "assigned", "project_id": project_id,
                "reviewer_username": request.reviewer_username.strip()}
    finally:
        connection.close()


def _repository_name(repo_url: str) -> str:
    parsed = urlparse(repo_url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise HTTPException(status_code=422, detail="Use an HTTPS github.com repository URL.")
    full_name = parsed.path.strip("/")
    if full_name.endswith(".git"):
        full_name = full_name[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name):
        raise HTTPException(status_code=422, detail="GitHub URL must contain owner/repository.")
    return full_name.lower()


def _process_pull_request_event(connection, *, payload: dict, project_id: str,
                                repository: str, event_type: str) -> dict:
    pull_request = payload.get("pull_request") or {}
    pull_number = int(payload.get("number") or pull_request.get("number") or 0)
    if not pull_number:
        return {"status": "ignored", "reason": "Pull request number is missing."}
    title = str(pull_request.get("title") or "")
    branch = str((pull_request.get("head") or {}).get("ref") or "")
    body = str(pull_request.get("body") or "")
    match = TASK_REFERENCE_RE.search(f"{branch} {title} {body}")
    task_id = int(match.group("number") or match.group("short")) if match else None
    if match and match.group("key") and match.group("key").lower() != f"{project_id}-TASK-".lower():
        task_id = None
    author_login = str((pull_request.get("user") or {}).get("login") or "").lower() or None
    identity = connection.execute(
        "SELECT student_id FROM student_github_identities WHERE project_id=? AND github_login=?",
        (project_id, author_login),
    ).fetchone() if author_login else None
    student_id = identity[0] if identity else None
    action = str(payload.get("action") or "").lower()
    merged = bool(pull_request.get("merged"))
    review_state = str((payload.get("review") or {}).get("state") or "").lower()
    review_status = "APPROVED" if event_type == "pull_request_review" and review_state == "approved" else "PENDING"
    evidence_status = "UNMATCHED_TASK"
    percentage = 0.0
    progress_status = "NOT_STARTED"
    if task_id is not None:
        try:
            task = _latest_task(connection, project_id, task_id)
            assignment = connection.execute(
                "SELECT assigned_to FROM task_assignments WHERE project_id=? AND task_id=?",
                (project_id, task_id),
            ).fetchone()
            evidence_status, authoritative_assignee = _github_assignment_decision(
                task, assignment[0] if assignment else task.get("assigned_to"), student_id,
            )
            current = connection.execute(
                "SELECT progress_percentage, status FROM task_progress WHERE project_id=? AND task_id=?",
                (project_id, task_id),
            ).fetchone()
            current_pct = float(current[0]) if current else 0.0
            current_status = current[1] if current else "NOT_STARTED"
            if merged:
                percentage, progress_status = 100.0, "COMPLETED"
                review_status = "MERGED"
            elif review_status == "APPROVED":
                percentage, progress_status = max(current_pct, 90.0), "IN_REVIEW"
            elif action in {"opened", "reopened", "synchronize", "ready_for_review"}:
                percentage, progress_status = max(current_pct, 60.0), "IN_REVIEW"
            else:
                percentage, progress_status = current_pct, current_status
            if evidence_status == "LINKED":
                previous = _set_progress(
                    connection, project_id=project_id, task_id=task_id,
                    assigned_to=authoritative_assignee, status=progress_status,
                    percentage=percentage, source="GITHUB_PR", actor=author_login or "github",
                )
                event_name = "PULL_REQUEST_MERGED" if merged else (
                    "PULL_REQUEST_APPROVED" if review_status == "APPROVED" else "PULL_REQUEST_UPDATED"
                )
            else:
                previous = current_pct
                percentage, progress_status = current_pct, current_status
                event_name = "GITHUB_EVIDENCE_REJECTED"
            _record_event(
                connection, project_id=project_id, task_id=task_id, event_type=event_name,
                source="GITHUB", actor_id=author_login, evidence_id=f"PR-{pull_number}",
                previous_progress=previous, new_progress=percentage,
                metadata={"repository": repository, "pull_number": pull_number,
                          "title": title, "action": action, "review_state": review_state,
                          "merged": merged, "author_mapped": bool(student_id),
                          "evidence_status": evidence_status,
                          "assigned_to": authoritative_assignee},
            )
        except HTTPException:
            evidence_status = "UNKNOWN_TASK"
    connection.execute(
        """INSERT INTO github_pull_requests
           (project_id, repository_full_name, pull_number, task_id, task_key, author_login,
            linked_student_id, title, branch, html_url, state, review_status, evidence_status,
            merged, opened_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(repository_full_name, pull_number) DO UPDATE SET
             task_id=excluded.task_id, task_key=excluded.task_key,
             linked_student_id=excluded.linked_student_id, title=excluded.title,
             branch=excluded.branch, html_url=excluded.html_url, state=excluded.state,
             review_status=CASE WHEN excluded.review_status='PENDING'
               THEN github_pull_requests.review_status ELSE excluded.review_status END,
             evidence_status=excluded.evidence_status,
             merged=excluded.merged,
             updated_at=excluded.updated_at""",
        (project_id, repository, pull_number, task_id,
         _task_key(project_id, task_id) if task_id is not None else None,
         author_login, student_id, title, branch, pull_request.get("html_url"),
         pull_request.get("state"), review_status, evidence_status, merged,
         pull_request.get("created_at"), pull_request.get("updated_at")),
    )
    return {"status": "processed", "project_id": project_id,
            "pull_number": pull_number, "task_id": task_id,
            "evidence_status": evidence_status, "progress_percentage": percentage}


@router.post("/api/github/register")
def register_github(request: GithubRegistrationRequest,
                    user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    project_id = _normalise_project_id(request.project_id)
    full_name = _repository_name(request.repo_url)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        connection.execute("DELETE FROM github_registrations WHERE project_id=?", (project_id,))
        connection.execute(
            """INSERT INTO github_registrations(project_id, repo_url, repository_full_name, registered_at)
               VALUES (?,?,?,?)""", (project_id, request.repo_url.strip(), full_name, _now().isoformat()),
        )
        connection.commit()
        return {"status": "registered", "project_id": project_id,
                "repo_url": request.repo_url.strip(), "repository_full_name": full_name,
                "webhook_url": "/api/webhooks/github",
                "webhook_secret_configured": bool(os.getenv("IPMS_GITHUB_WEBHOOK_SECRET", "").strip())}
    finally:
        connection.close()


@router.get("/api/github/status")
def github_status(project_id: str, user: AuthenticatedUser = Depends(current_user)):
    project_id = _normalise_project_id(project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        row = connection.execute(
            """SELECT repo_url, repository_full_name, registered_at FROM github_registrations
               WHERE project_id=? ORDER BY id DESC LIMIT 1""", (project_id,),
        ).fetchone()
        if not row:
            return {"connected": False}
        return {"connected": True, "repo_url": row[0], "repository_full_name": row[1],
                "registered_at": row[2],
                "webhook_secret_configured": bool(os.getenv("IPMS_GITHUB_WEBHOOK_SECRET", "").strip())}
    finally:
        connection.close()


@router.post("/api/github/identities")
def register_github_identity(request: GithubIdentityRequest,
                             user: AuthenticatedUser = Depends(require_roles("staff", "supervisor"))):
    project_id = _normalise_project_id(request.project_id)
    connection = connect()
    try:
        _can_review(connection, project_id, user)
        connection.execute(
            """INSERT INTO student_github_identities(project_id, student_id, github_login)
               VALUES (?,?,?) ON CONFLICT(project_id, student_id) DO UPDATE SET
               github_login=excluded.github_login, registered_at=NOW()""",
            (project_id, request.student_id.strip(), request.github_login.strip().lower()),
        )
        connection.commit()
        return {"status": "registered"}
    finally:
        connection.close()


@router.post("/api/webhooks/github")
async def github_webhook(request: Request,
                         x_hub_signature_256: str | None = Header(default=None),
                         x_github_delivery: str | None = Header(default=None),
                         x_github_event: str | None = Header(default=None)):
    secret = os.getenv("IPMS_GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="GitHub webhook secret is not configured.")
    body = await request.body()
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature.")
    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing GitHub delivery ID.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid GitHub JSON payload.") from exc
    repository = str(payload.get("repository", {}).get("full_name", "")).lower()
    connection = connect()
    try:
        registration = connection.execute(
            "SELECT project_id FROM github_registrations WHERE repository_full_name=?",
            (repository,),
        ).fetchone()
        if not registration:
            raise HTTPException(status_code=404, detail="Repository is not registered to an IPMS group.")
        project_id = registration[0]
        delivery_cursor = connection.execute(
            """INSERT INTO github_webhook_deliveries(delivery_id, repository_full_name, event_type)
               VALUES (?,?,?) ON CONFLICT(delivery_id) DO NOTHING RETURNING id""",
            (x_github_delivery, repository, x_github_event or "unknown"),
        )
        if not delivery_cursor.fetchone():
            connection.rollback()
            return {"status": "duplicate", "delivery_id": x_github_delivery}
        if x_github_event == "ping":
            connection.commit()
            return {"status": "ok", "event": "ping"}
        if x_github_event in {"pull_request", "pull_request_review"}:
            result = _process_pull_request_event(
                connection, payload=payload, project_id=project_id,
                repository=repository, event_type=x_github_event,
            )
            connection.commit()
            return result
        if x_github_event != "push":
            connection.commit()
            return {"status": "ignored", "event": x_github_event}
        processed, linked, unmatched = 0, 0, 0
        branch = str(payload.get("ref", "")).removeprefix("refs/heads/")
        for commit in payload.get("commits", []):
            sha = str(commit.get("id", "")).strip()
            if not sha:
                continue
            message = str(commit.get("message", ""))
            match = TASK_REFERENCE_RE.search(f"{branch} {message}")
            task_id = int(match.group("number") or match.group("short")) if match else None
            if match and match.group("key"):
                referenced_prefix = match.group("key").lower()
                expected_prefix = f"{project_id}-TASK-".lower()
                if referenced_prefix != expected_prefix:
                    task_id = None
            task_key = _task_key(project_id, task_id) if task_id is not None else None
            author = commit.get("author") or {}
            author_login = str(author.get("username") or "").lower() or None
            author_email = str(author.get("email") or "") or None
            identity = connection.execute(
                """SELECT student_id FROM student_github_identities
                   WHERE project_id=? AND github_login=?""", (project_id, author_login),
            ).fetchone() if author_login else None
            student_id = identity[0] if identity else None
            evidence_status = "UNMATCHED_TASK"
            if task_id is not None:
                try:
                    task = _latest_task(connection, project_id, task_id)
                    assignment = connection.execute(
                        "SELECT assigned_to FROM task_assignments WHERE project_id=? AND task_id=?",
                        (project_id, task_id),
                    ).fetchone()
                    evidence_status, authoritative_assignee = _github_assignment_decision(
                        task, assignment[0] if assignment else task.get("assigned_to"), student_id,
                    )
                    current = connection.execute(
                        "SELECT progress_percentage, status FROM task_progress WHERE project_id=? AND task_id=?",
                        (project_id, task_id),
                    ).fetchone()
                    current_pct = float(current[0]) if current else 0.0
                    current_status = current[1] if current else "NOT_STARTED"
                    new_pct = min(100.0, max(current_pct, 10.0))
                    progress_status = current_status if current_status in {"COMPLETED", "APPROVED"} else "IN_PROGRESS"
                    if evidence_status == "LINKED":
                        previous = _set_progress(
                            connection, project_id=project_id, task_id=task_id,
                            assigned_to=authoritative_assignee, status=progress_status,
                            percentage=new_pct, source="GITHUB", actor=author_login or "github",
                        )
                        event_name = "GITHUB_COMMIT_RECEIVED"
                        linked += 1
                    else:
                        previous = current_pct
                        new_pct, progress_status = current_pct, current_status
                        event_name = "GITHUB_EVIDENCE_REJECTED"
                        unmatched += 1
                    _record_event(
                        connection, project_id=project_id, task_id=task_id,
                        event_type=event_name, source="GITHUB",
                        actor_id=author_login, evidence_id=sha,
                        previous_progress=previous, new_progress=new_pct,
                        metadata={"repository": repository, "branch": branch,
                                  "message": message, "author_mapped": bool(student_id),
                                  "evidence_status": evidence_status,
                                  "assigned_to": authoritative_assignee},
                    )
                except HTTPException:
                    evidence_status = "UNKNOWN_TASK"
                    unmatched += 1
            else:
                unmatched += 1
            connection.execute(
                """INSERT INTO github_commits
                   (project_id, repository_full_name, commit_sha, author_login, author_email,
                   message, branch, task_id, task_key, linked_student_id, evidence_status, committed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
                (project_id, repository, sha, author_login, author_email, message, branch,
                 task_id, task_key, student_id, evidence_status, commit.get("timestamp")),
            )
            processed += 1
        connection.commit()
        return {"status": "processed", "project_id": project_id,
                "commits_processed": processed, "linked": linked, "unmatched": unmatched}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
