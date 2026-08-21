"""Small sqlite3 repository helpers for Phase 1 supervisor workflow storage."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid4())


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _fetch_one(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    return _row_to_dict(connection.execute(query, params).fetchone())


def _fetch_all(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def _version_belongs_to_proposal(connection: sqlite3.Connection, proposal_id: str, version_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM proposal_versions WHERE proposal_id = ? AND version_id = ?",
        (proposal_id, version_id),
    ).fetchone()
    return row is not None


def create_user(
    connection: sqlite3.Connection,
    *,
    email: str,
    role: str,
    display_name: str,
    password_hash: str | None = None,
    user_id: str | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    now = _utc_now()
    resolved_id = user_id or _new_id()
    connection.execute(
        """
        INSERT INTO users (user_id, email, password_hash, role, display_name, created_at, updated_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (resolved_id, email, password_hash, role, display_name, now, now, int(is_active)),
    )
    connection.commit()
    return get_user(connection, resolved_id)


def get_user(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM users WHERE user_id = ?", (user_id,))


def get_user_by_email(connection: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM users WHERE email = ?", (email,))


def update_user_password_hash(connection: sqlite3.Connection, *, user_id: str, password_hash: str) -> dict[str, Any]:
    connection.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
        (password_hash, _utc_now(), user_id),
    )
    connection.commit()
    return get_user(connection, user_id)


def create_supervisor_account(
    connection: sqlite3.Connection,
    *,
    email: str,
    display_name: str,
    password_hash: str,
) -> dict[str, Any]:
    now = _utc_now()
    user_id = _new_id()
    supervisor_id = _new_id()
    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            INSERT INTO users (user_id, email, password_hash, role, display_name, created_at, updated_at, is_active)
            VALUES (?, ?, ?, 'supervisor', ?, ?, ?, 1)
            """,
            (user_id, email, password_hash, display_name, now, now),
        )
        connection.execute(
            """
            INSERT INTO supervisor_profiles (supervisor_id, user_id, department, title)
            VALUES (?, ?, NULL, NULL)
            """,
            (supervisor_id, user_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return get_supervisor_identity_by_user_id(connection, user_id)


def create_supervisor_profile(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    department: str | None = None,
    title: str | None = None,
    supervisor_id: str | None = None,
) -> dict[str, Any]:
    resolved_id = supervisor_id or _new_id()
    connection.execute(
        """
        INSERT INTO supervisor_profiles (supervisor_id, user_id, department, title)
        VALUES (?, ?, ?, ?)
        """,
        (resolved_id, user_id, department, title),
    )
    connection.commit()
    return get_supervisor_profile(connection, resolved_id)


def get_supervisor_profile(connection: sqlite3.Connection, supervisor_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM supervisor_profiles WHERE supervisor_id = ?", (supervisor_id,))


def get_supervisor_profile_by_user_id(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM supervisor_profiles WHERE user_id = ?", (user_id,))


def get_supervisor_identity_by_user_id(connection: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT users.user_id, users.email, users.role, users.display_name, users.is_active,
               supervisor_profiles.supervisor_id, supervisor_profiles.department, supervisor_profiles.title
        FROM users
        JOIN supervisor_profiles ON supervisor_profiles.user_id = users.user_id
        WHERE users.user_id = ?
          AND users.role = 'supervisor'
          AND users.is_active = 1
        """,
        (user_id,),
    )


def get_supervisor_identity_by_email(connection: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT users.user_id, users.email, users.role, users.display_name, users.password_hash, users.is_active,
               supervisor_profiles.supervisor_id, supervisor_profiles.department, supervisor_profiles.title
        FROM users
        JOIN supervisor_profiles ON supervisor_profiles.user_id = users.user_id
        WHERE users.email = ?
          AND users.role = 'supervisor'
          AND users.is_active = 1
        """,
        (email,),
    )


def create_student(
    connection: sqlite3.Connection,
    *,
    academic_student_id: str,
    full_name: str,
    email: str | None = None,
    program: str | None = None,
    cohort: str | None = None,
    student_id: str | None = None,
    active: bool = True,
) -> dict[str, Any]:
    now = _utc_now()
    resolved_id = student_id or _new_id()
    connection.execute(
        """
        INSERT INTO students (
            student_id, academic_student_id, full_name, email, program, cohort, created_at, updated_at, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (resolved_id, academic_student_id, full_name, email, program, cohort, now, now, int(active)),
    )
    connection.commit()
    return get_student(connection, resolved_id)


def get_student(connection: sqlite3.Connection, student_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM students WHERE student_id = ?", (student_id,))


def get_student_by_academic_id(connection: sqlite3.Connection, academic_student_id: str) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        "SELECT * FROM students WHERE academic_student_id = ?",
        (academic_student_id,),
    )


def assign_supervisor_to_student(
    connection: sqlite3.Connection,
    *,
    supervisor_id: str,
    student_id: str,
    assignment_role: str = "primary_supervisor",
    assignment_id: str | None = None,
    active: bool = True,
) -> dict[str, Any]:
    resolved_id = assignment_id or _new_id()
    connection.execute(
        """
        INSERT INTO supervisor_student_assignments (
            assignment_id, supervisor_id, student_id, assignment_role, assigned_at, active
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (resolved_id, supervisor_id, student_id, assignment_role, _utc_now(), int(active)),
    )
    connection.commit()
    return _fetch_one(
        connection,
        "SELECT * FROM supervisor_student_assignments WHERE assignment_id = ?",
        (resolved_id,),
    )


def get_supervisor_students(connection: sqlite3.Connection, supervisor_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT students.*, supervisor_student_assignments.assignment_id,
               supervisor_student_assignments.assignment_role,
               supervisor_student_assignments.assigned_at
        FROM supervisor_student_assignments
        JOIN students ON students.student_id = supervisor_student_assignments.student_id
        WHERE supervisor_student_assignments.supervisor_id = ?
          AND supervisor_student_assignments.active = 1
          AND students.active = 1
        ORDER BY students.full_name
        """,
        (supervisor_id,),
    )


def get_supervisor_dashboard_summary(connection: sqlite3.Connection, supervisor_id: str) -> dict[str, Any]:
    students = get_supervisor_students(connection, supervisor_id)
    recent_proposals: list[dict[str, Any]] = []
    students_with_proposals = set()
    analyzed_current_versions = 0
    waiting_for_analysis = 0
    revision_requested = 0
    reviewed = 0

    for student in students:
        proposals = get_student_proposals(connection, student["student_id"])
        if proposals:
            students_with_proposals.add(student["student_id"])
        for proposal in proposals:
            current_version = None
            current_version_id = proposal.get("current_version_id")
            if current_version_id:
                current_version = get_proposal_version(connection, current_version_id)
            analyses = get_version_analyses(connection, current_version["version_id"]) if current_version else []
            latest_review = (
                get_latest_supervisor_review(
                    connection,
                    version_id=current_version["version_id"],
                    supervisor_id=supervisor_id,
                )
                if current_version
                else None
            )
            if current_version:
                if analyses:
                    analyzed_current_versions += 1
                else:
                    waiting_for_analysis += 1
            if latest_review:
                reviewed += 1
                if latest_review.get("decision") in {"REQUEST_REVISION", "REVISION_REQUESTED"}:
                    revision_requested += 1

            review_decision = latest_review.get("decision") if latest_review else None
            recent_proposals.append(
                {
                    "student_id": student["student_id"],
                    "student_name": student["full_name"],
                    "academic_student_id": student["academic_student_id"],
                    "proposal_id": proposal["proposal_id"],
                    "proposal_title": proposal["title"],
                    "current_version_id": current_version["version_id"] if current_version else None,
                    "current_version_number": current_version["version_number"] if current_version else None,
                    "last_upload": (
                        current_version.get("submitted_at")
                        or current_version.get("created_at")
                        if current_version
                        else proposal.get("updated_at")
                    ),
                    "analysis_state": "Analyzed" if analyses else ("Waiting for analysis" if current_version else "No version"),
                    "supervisor_review_state": review_decision or "Not reviewed",
                }
            )

    recent_proposals.sort(key=lambda item: item.get("last_upload") or "", reverse=True)
    return {
        "assigned_students": len(students),
        "with_proposals": len(students_with_proposals),
        "analyzed_current_versions": analyzed_current_versions,
        "waiting_for_analysis": waiting_for_analysis,
        "revision_requested": revision_requested,
        "reviewed": reviewed,
        "recent_proposals": recent_proposals[:6],
    }


def get_student_supervisors(connection: sqlite3.Connection, student_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT supervisor_profiles.*, users.display_name, users.email,
               supervisor_student_assignments.assignment_id,
               supervisor_student_assignments.assignment_role,
               supervisor_student_assignments.assigned_at
        FROM supervisor_student_assignments
        JOIN supervisor_profiles ON supervisor_profiles.supervisor_id = supervisor_student_assignments.supervisor_id
        JOIN users ON users.user_id = supervisor_profiles.user_id
        WHERE supervisor_student_assignments.student_id = ?
          AND supervisor_student_assignments.active = 1
          AND users.is_active = 1
        ORDER BY supervisor_student_assignments.assignment_role, users.display_name
        """,
        (student_id,),
    )


def get_supervisor_student_assignment(
    connection: sqlite3.Connection,
    *,
    supervisor_id: str,
    student_id: str,
    assignment_role: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT * FROM supervisor_student_assignments
        WHERE supervisor_id = ?
          AND student_id = ?
          AND assignment_role = ?
          AND active = 1
        """,
        (supervisor_id, student_id, assignment_role),
    )


def get_active_supervisor_student_assignment(
    connection: sqlite3.Connection,
    *,
    supervisor_id: str,
    student_id: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT * FROM supervisor_student_assignments
        WHERE supervisor_id = ?
          AND student_id = ?
          AND active = 1
        ORDER BY assigned_at DESC
        LIMIT 1
        """,
        (supervisor_id, student_id),
    )


def remove_supervisor_student_assignment(
    connection: sqlite3.Connection,
    *,
    supervisor_id: str,
    student_id: str,
) -> dict[str, Any] | None:
    assignment = get_active_supervisor_student_assignment(
        connection,
        supervisor_id=supervisor_id,
        student_id=student_id,
    )
    if assignment is None:
        return None
    connection.execute(
        """
        UPDATE supervisor_student_assignments
        SET active = 0
        WHERE supervisor_id = ?
          AND student_id = ?
          AND active = 1
        """,
        (supervisor_id, student_id),
    )
    connection.commit()
    return _fetch_one(
        connection,
        "SELECT * FROM supervisor_student_assignments WHERE assignment_id = ?",
        (assignment["assignment_id"],),
    )


def supervisor_is_assigned_to_student(connection: sqlite3.Connection, *, supervisor_id: str, student_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM supervisor_student_assignments
        WHERE supervisor_id = ?
          AND student_id = ?
          AND active = 1
        """,
        (supervisor_id, student_id),
    ).fetchone()
    return row is not None


def create_proposal(
    connection: sqlite3.Connection,
    *,
    student_id: str,
    title: str,
    status: str = "DRAFT",
    proposal_id: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    resolved_id = proposal_id or _new_id()
    connection.execute(
        """
        INSERT INTO proposals (proposal_id, student_id, title, status, current_version_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, NULL, ?, ?)
        """,
        (resolved_id, student_id, title, status, now, now),
    )
    connection.commit()
    return get_proposal(connection, resolved_id)


def get_proposal(connection: sqlite3.Connection, proposal_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,))


def get_student_proposal_by_title(connection: sqlite3.Connection, student_id: str, title: str) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        "SELECT * FROM proposals WHERE student_id = ? AND title = ?",
        (student_id, title),
    )


def get_student_proposals(connection: sqlite3.Connection, student_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        "SELECT * FROM proposals WHERE student_id = ? ORDER BY created_at",
        (student_id,),
    )


def delete_proposal_tree(connection: sqlite3.Connection, proposal_id: str) -> dict[str, int]:
    """Hard-delete one proposal and SQLite-owned workflow dependents."""
    counts: dict[str, int] = {}
    try:
        connection.execute("BEGIN")
        cursor = connection.execute(
            """
            DELETE FROM supervisor_review_drafts
            WHERE version_id IN (
                SELECT version_id FROM proposal_versions WHERE proposal_id = ?
            )
            """,
            (proposal_id,),
        )
        counts["supervisor_review_drafts"] = cursor.rowcount
        for table in (
            "notification_logs",
            "ai_supervisor_review_drafts",
            "supervisor_reviews",
            "analyses",
            "proposal_versions",
            "proposals",
        ):
            cursor = connection.execute(f"DELETE FROM {table} WHERE proposal_id = ?", (proposal_id,))
            counts[table] = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return counts


def create_proposal_version(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    version_number: int,
    original_filename: str | None = None,
    source_type: str | None = None,
    original_file_path: str | None = None,
    extracted_text: str | None = None,
    edited_text: str | None = None,
    submitted_at: str | None = None,
    status: str = "DRAFT",
    version_id: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    resolved_id = version_id or _new_id()
    connection.execute(
        """
        INSERT INTO proposal_versions (
            version_id, proposal_id, version_number, original_filename, source_type,
            original_file_path, extracted_text, edited_text, created_at, submitted_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resolved_id,
            proposal_id,
            version_number,
            original_filename,
            source_type,
            original_file_path,
            extracted_text,
            edited_text,
            now,
            submitted_at,
            status,
        ),
    )
    connection.execute(
        "UPDATE proposals SET current_version_id = ?, updated_at = ? WHERE proposal_id = ?",
        (resolved_id, now, proposal_id),
    )
    connection.commit()
    return get_proposal_version(connection, resolved_id)


def create_revised_proposal_version_after_revision_request(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    supervisor_id: str,
    original_filename: str | None = None,
    source_type: str | None = None,
    original_file_path: str | None = None,
    extracted_text: str | None = None,
    edited_text: str | None = None,
    submitted_at: str | None = None,
    status: str = "DRAFT",
    version_id: str | None = None,
) -> dict[str, Any]:
    """Create the next immutable proposal version after the current version requests revision."""
    now = _utc_now()
    resolved_id = version_id or _new_id()
    try:
        connection.execute("BEGIN IMMEDIATE")
        proposal = _fetch_one(connection, "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,))
        if proposal is None:
            raise ValueError("PROPOSAL_NOT_FOUND")
        current_version = _fetch_one(
            connection,
            """
            SELECT *
            FROM proposal_versions
            WHERE proposal_id = ?
            ORDER BY version_number DESC, created_at DESC, version_id DESC
            LIMIT 1
            """,
            (proposal_id,),
        )
        if current_version is None:
            raise ValueError("CURRENT_VERSION_NOT_FOUND")
        latest_review = get_latest_supervisor_review(
            connection,
            version_id=current_version["version_id"],
            supervisor_id=supervisor_id,
        )
        if latest_review is None or latest_review.get("decision") != "REVISION_REQUESTED":
            raise ValueError("REVISION_NOT_REQUESTED")
        row = connection.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM proposal_versions WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        next_version = int(row["next_version"])
        connection.execute(
            """
            INSERT INTO proposal_versions (
                version_id, proposal_id, version_number, original_filename, source_type,
                original_file_path, extracted_text, edited_text, created_at, submitted_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_id,
                proposal_id,
                next_version,
                original_filename,
                source_type,
                original_file_path,
                extracted_text,
                edited_text,
                now,
                submitted_at,
                status,
            ),
        )
        connection.execute(
            "UPDATE proposals SET current_version_id = ?, updated_at = ? WHERE proposal_id = ?",
            (resolved_id, now, proposal_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return get_proposal_version(connection, resolved_id)


def get_proposal_version(connection: sqlite3.Connection, version_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM proposal_versions WHERE version_id = ?", (version_id,))


def get_proposal_versions(connection: sqlite3.Connection, proposal_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        "SELECT * FROM proposal_versions WHERE proposal_id = ? ORDER BY version_number",
        (proposal_id,),
    )


def get_proposal_version_by_number(
    connection: sqlite3.Connection,
    proposal_id: str,
    version_number: int,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        "SELECT * FROM proposal_versions WHERE proposal_id = ? AND version_number = ?",
        (proposal_id, version_number),
    )


def create_analysis(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    version_id: str,
    request_id: str | None = None,
    source: str | None = None,
    input_text_snapshot: str | None = None,
    analysis_id: str | None = None,
) -> dict[str, Any]:
    if not _version_belongs_to_proposal(connection, proposal_id, version_id):
        raise ValueError("version_id does not belong to proposal_id")

    resolved_id = analysis_id or _new_id()
    connection.execute(
        """
        INSERT INTO analyses (
            analysis_id, proposal_id, version_id, request_id, created_at, source, input_text_snapshot
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (resolved_id, proposal_id, version_id, request_id, _utc_now(), source, input_text_snapshot),
    )
    connection.commit()
    return _fetch_one(connection, "SELECT * FROM analyses WHERE analysis_id = ?", (resolved_id,))


def get_analysis(connection: sqlite3.Connection, analysis_id: str) -> dict[str, Any] | None:
    return _fetch_one(connection, "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,))


def get_version_analyses(connection: sqlite3.Connection, version_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        "SELECT * FROM analyses WHERE version_id = ? ORDER BY created_at",
        (version_id,),
    )


def create_supervisor_review(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    version_id: str,
    supervisor_id: str,
    decision: str,
    overall_comment: str | None = None,
    review_id: str | None = None,
) -> dict[str, Any]:
    if not _version_belongs_to_proposal(connection, proposal_id, version_id):
        raise ValueError("version_id does not belong to proposal_id")

    now = _utc_now()
    resolved_id = review_id or _new_id()
    connection.execute(
        """
        INSERT INTO supervisor_reviews (
            review_id, proposal_id, version_id, supervisor_id, decision, overall_comment, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (resolved_id, proposal_id, version_id, supervisor_id, decision, overall_comment, now, now),
    )
    connection.commit()
    return _fetch_one(connection, "SELECT * FROM supervisor_reviews WHERE review_id = ?", (resolved_id,))


def update_supervisor_review(
    connection: sqlite3.Connection,
    *,
    review_id: str,
    decision: str,
    overall_comment: str | None = None,
) -> dict[str, Any]:
    connection.execute(
        """
        UPDATE supervisor_reviews
        SET decision = ?, overall_comment = ?, updated_at = ?
        WHERE review_id = ?
        """,
        (decision, overall_comment, _utc_now(), review_id),
    )
    connection.commit()
    return _fetch_one(connection, "SELECT * FROM supervisor_reviews WHERE review_id = ?", (review_id,))


def get_latest_supervisor_review(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    supervisor_id: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT supervisor_reviews.*, users.display_name AS supervisor_name
        FROM supervisor_reviews
        JOIN supervisor_profiles ON supervisor_profiles.supervisor_id = supervisor_reviews.supervisor_id
        JOIN users ON users.user_id = supervisor_profiles.user_id
        WHERE supervisor_reviews.version_id = ?
          AND supervisor_reviews.supervisor_id = ?
        ORDER BY supervisor_reviews.updated_at DESC, supervisor_reviews.created_at DESC, supervisor_reviews.review_id DESC
        LIMIT 1
        """,
        (version_id, supervisor_id),
    )


def save_current_supervisor_review(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    version_id: str,
    supervisor_id: str,
    decision: str,
    overall_comment: str | None = None,
) -> dict[str, Any]:
    latest = get_latest_supervisor_review(connection, version_id=version_id, supervisor_id=supervisor_id)
    if latest:
        return update_supervisor_review(
            connection,
            review_id=latest["review_id"],
            decision=decision,
            overall_comment=overall_comment,
        )
    return create_supervisor_review(
        connection,
        proposal_id=proposal_id,
        version_id=version_id,
        supervisor_id=supervisor_id,
        decision=decision,
        overall_comment=overall_comment,
    )


def get_version_reviews(connection: sqlite3.Connection, version_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT supervisor_reviews.*, users.display_name AS supervisor_name
        FROM supervisor_reviews
        JOIN supervisor_profiles ON supervisor_profiles.supervisor_id = supervisor_reviews.supervisor_id
        JOIN users ON users.user_id = supervisor_profiles.user_id
        WHERE supervisor_reviews.version_id = ?
        ORDER BY supervisor_reviews.created_at
        """,
        (version_id,),
    )


def create_ai_supervisor_review_draft(
    connection: sqlite3.Connection,
    *,
    proposal_id: str,
    version_id: str,
    analysis_id: str,
    draft: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    llm_metadata: dict[str, Any] | None = None,
    draft_id: str | None = None,
) -> dict[str, Any]:
    if not _version_belongs_to_proposal(connection, proposal_id, version_id):
        raise ValueError("version_id does not belong to proposal_id")

    now = _utc_now()
    resolved_id = draft_id or _new_id()
    connection.execute(
        """
        INSERT INTO ai_supervisor_review_drafts (
            draft_id, proposal_id, version_id, analysis_id,
            draft_json, evidence_json, llm_metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resolved_id,
            proposal_id,
            version_id,
            analysis_id,
            json.dumps(draft, ensure_ascii=False),
            json.dumps(evidence or {}, ensure_ascii=False),
            json.dumps(llm_metadata or {}, ensure_ascii=False),
            now,
            now,
        ),
    )
    connection.commit()
    return get_ai_supervisor_review_draft(connection, version_id=version_id, analysis_id=analysis_id)


def get_ai_supervisor_review_draft(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    analysis_id: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT * FROM ai_supervisor_review_drafts
        WHERE version_id = ? AND analysis_id = ?
        """,
        (version_id, analysis_id),
    )


def get_supervisor_review_draft(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT * FROM supervisor_review_drafts
        WHERE version_id = ? AND analysis_id = ? AND supervisor_id = ?
        """,
        (version_id, analysis_id, supervisor_id),
    )


def save_supervisor_review_draft(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    ai_draft_id: str,
    overall_assessment: str,
    strengths: list[str],
    areas_requiring_improvement: list[str],
    methodology_feedback: str,
    evaluation_validation_feedback: str,
    recommendations: list[str],
    suggested_revision_instructions: list[str],
    supervisor_comments: str | None = None,
    review_id: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    existing = get_supervisor_review_draft(
        connection,
        version_id=version_id,
        analysis_id=analysis_id,
        supervisor_id=supervisor_id,
    )
    if existing:
        connection.execute(
            """
            UPDATE supervisor_review_drafts
            SET ai_draft_id = ?,
                overall_assessment = ?,
                strengths_json = ?,
                areas_requiring_improvement_json = ?,
                methodology_feedback = ?,
                evaluation_validation_feedback = ?,
                recommendations_json = ?,
                suggested_revision_instructions_json = ?,
                supervisor_comments = ?,
                updated_at = ?
            WHERE review_id = ?
            """,
            (
                ai_draft_id,
                overall_assessment,
                json.dumps(strengths, ensure_ascii=False),
                json.dumps(areas_requiring_improvement, ensure_ascii=False),
                methodology_feedback,
                evaluation_validation_feedback,
                json.dumps(recommendations, ensure_ascii=False),
                json.dumps(suggested_revision_instructions, ensure_ascii=False),
                supervisor_comments,
                now,
                existing["review_id"],
            ),
        )
        connection.commit()
        return get_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
        )

    resolved_id = review_id or _new_id()
    connection.execute(
        """
        INSERT INTO supervisor_review_drafts (
            review_id, version_id, analysis_id, supervisor_id, ai_draft_id,
            overall_assessment, strengths_json, areas_requiring_improvement_json,
            methodology_feedback, evaluation_validation_feedback, recommendations_json,
            suggested_revision_instructions_json, supervisor_comments, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resolved_id,
            version_id,
            analysis_id,
            supervisor_id,
            ai_draft_id,
            overall_assessment,
            json.dumps(strengths, ensure_ascii=False),
            json.dumps(areas_requiring_improvement, ensure_ascii=False),
            methodology_feedback,
            evaluation_validation_feedback,
            json.dumps(recommendations, ensure_ascii=False),
            json.dumps(suggested_revision_instructions, ensure_ascii=False),
            supervisor_comments,
            now,
            now,
        ),
    )
    connection.commit()
    return get_supervisor_review_draft(
        connection,
        version_id=version_id,
        analysis_id=analysis_id,
        supervisor_id=supervisor_id,
    )


def create_notification_log(
    connection: sqlite3.Connection,
    *,
    student_id: str,
    proposal_id: str,
    notification_type: str,
    status: str,
    version_id: str | None = None,
    analysis_id: str | None = None,
    supervisor_id: str | None = None,
    supervisor_review_draft_id: str | None = None,
    review_id: str | None = None,
    recipient_email: str | None = None,
    subject: str | None = None,
    sent_at: str | None = None,
    error_message: str | None = None,
    notification_id: str | None = None,
) -> dict[str, Any]:
    resolved_id = notification_id or _new_id()
    connection.execute(
        """
        INSERT INTO notification_logs (
            notification_id, student_id, proposal_id, version_id, analysis_id,
            supervisor_id, supervisor_review_draft_id, review_id, recipient_email,
            subject, notification_type, status, created_at, sent_at, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            resolved_id,
            student_id,
            proposal_id,
            version_id,
            analysis_id,
            supervisor_id,
            supervisor_review_draft_id,
            review_id,
            recipient_email,
            subject,
            notification_type,
            status,
            _utc_now(),
            sent_at,
            error_message,
        ),
    )
    connection.commit()
    return _fetch_one(connection, "SELECT * FROM notification_logs WHERE notification_id = ?", (resolved_id,))


def get_version_notifications(connection: sqlite3.Connection, version_id: str) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        "SELECT * FROM notification_logs WHERE version_id = ? ORDER BY created_at",
        (version_id,),
    )


def get_feedback_delivery_notifications(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
) -> list[dict[str, Any]]:
    return _fetch_all(
        connection,
        """
        SELECT * FROM notification_logs
        WHERE version_id = ?
          AND analysis_id = ?
          AND supervisor_id = ?
          AND notification_type = 'FEEDBACK_SENT'
        ORDER BY created_at DESC
        """,
        (version_id, analysis_id, supervisor_id),
    )


def get_successful_feedback_delivery(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    supervisor_review_draft_id: str,
) -> dict[str, Any] | None:
    return _fetch_one(
        connection,
        """
        SELECT * FROM notification_logs
        WHERE version_id = ?
          AND analysis_id = ?
          AND supervisor_id = ?
          AND supervisor_review_draft_id = ?
          AND notification_type = 'FEEDBACK_SENT'
          AND status = 'SENT'
        ORDER BY sent_at DESC, created_at DESC
        LIMIT 1
        """,
        (version_id, analysis_id, supervisor_id, supervisor_review_draft_id),
    )
