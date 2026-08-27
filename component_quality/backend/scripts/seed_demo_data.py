"""Seed local-only supervisor workflow demo data.

This script is intentionally manual. It writes to PostgreSQL through DATABASE_URL
and never runs during FastAPI startup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.session import get_session
from src.db.repositories import (
    assign_supervisor_to_student,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_user,
    get_proposal_version_by_number,
    get_student_by_academic_id,
    get_student_proposal_by_title,
    get_supervisor_profile_by_user_id,
    get_supervisor_student_assignment,
    get_user_by_email,
)


SUPERVISOR_EMAIL = "supervisor@example.test"


def _ensure_supervisor(connection) -> dict[str, Any]:
    user = get_user_by_email(connection, SUPERVISOR_EMAIL)
    if user is None:
        user = create_user(
            connection,
            email=SUPERVISOR_EMAIL,
            role="supervisor",
            display_name="Dr. Demo Supervisor",
        )

    supervisor = get_supervisor_profile_by_user_id(connection, user["user_id"])
    if supervisor is None:
        supervisor = create_supervisor_profile(
            connection,
            user_id=user["user_id"],
            department="Computing",
            title="Dr.",
        )
    return supervisor


def _ensure_student(connection, *, academic_id: str, full_name: str, email: str) -> dict[str, Any]:
    student = get_student_by_academic_id(connection, academic_id)
    if student is None:
        student = create_student(
            connection,
            academic_student_id=academic_id,
            full_name=full_name,
            email=email,
            program="Information Technology",
            cohort="2022",
        )
    return student


def _ensure_assignment(connection, *, supervisor_id: str, student_id: str) -> dict[str, Any]:
    assignment = get_supervisor_student_assignment(
        connection,
        supervisor_id=supervisor_id,
        student_id=student_id,
        assignment_role="primary_supervisor",
    )
    if assignment is None:
        assignment = assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_id,
            student_id=student_id,
            assignment_role="primary_supervisor",
        )
    return assignment


def _ensure_proposal(connection, *, student_id: str, title: str) -> dict[str, Any]:
    proposal = get_student_proposal_by_title(connection, student_id, title)
    if proposal is None:
        proposal = create_proposal(connection, student_id=student_id, title=title, status="DRAFT")
    return proposal


def _ensure_version(
    connection,
    *,
    proposal_id: str,
    version_number: int,
    extracted_text: str,
    original_filename: str = "demo-proposal.pdf",
) -> dict[str, Any]:
    version = get_proposal_version_by_number(connection, proposal_id, version_number)
    if version is None:
        version = create_proposal_version(
            connection,
            proposal_id=proposal_id,
            version_number=version_number,
            original_filename=original_filename,
            source_type="pdf",
            extracted_text=extracted_text,
            status="DRAFT",
        )
    return version


def seed_demo_data() -> dict[str, Any]:
    connection = get_session()
    try:
        supervisor = _ensure_supervisor(connection)
        students = [
            _ensure_student(
                connection,
                academic_id="IT22000001",
                full_name="Demo Student One",
                email="student.one@example.test",
            ),
            _ensure_student(
                connection,
                academic_id="IT22000002",
                full_name="Demo Student Two",
                email="student.two@example.test",
            ),
        ]

        for student in students:
            _ensure_assignment(connection, supervisor_id=supervisor["supervisor_id"], student_id=student["student_id"])

        proposal_one = _ensure_proposal(
            connection,
            student_id=students[0]["student_id"],
            title="AI-Assisted Research Proposal Evaluation",
        )
        _ensure_version(
            connection,
            proposal_id=proposal_one["proposal_id"],
            version_number=1,
            extracted_text="Version 1 draft with early methodology notes and incomplete evaluation planning.",
        )
        _ensure_version(
            connection,
            proposal_id=proposal_one["proposal_id"],
            version_number=2,
            extracted_text="Version 2 draft with refined objectives, literature review, and evaluation outline.",
        )

        proposal_two = _ensure_proposal(
            connection,
            student_id=students[1]["student_id"],
            title="Intelligent Academic Feedback System",
        )
        _ensure_version(
            connection,
            proposal_id=proposal_two["proposal_id"],
            version_number=1,
            extracted_text="Initial proposal draft focused on feedback classification and supervisor review workflows.",
        )

        return {
            "supervisor_id": supervisor["supervisor_id"],
            "students": students,
            "proposal_ids": [proposal_one["proposal_id"], proposal_two["proposal_id"]],
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local ResearchPilot supervisor demo data.")
    parser.parse_args()

    result = seed_demo_data()
    print("Seeded local supervisor workflow demo data.")
    print("Database: PostgreSQL DATABASE_URL")
    print(f"Supervisor ID: {result['supervisor_id']}")
    print("Use set_supervisor_password.py to configure local supervisor login credentials.")


if __name__ == "__main__":
    main()
