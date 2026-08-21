import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import connect
from src.db.repositories import (
    assign_supervisor_to_student,
    create_analysis,
    create_notification_log,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_supervisor_review,
    create_user,
    get_proposal_version,
    get_proposal_versions,
    get_student_by_academic_id,
    get_student_proposals,
    get_student_supervisors,
    get_supervisor_students,
    get_user,
    get_version_analyses,
    get_version_notifications,
    get_version_reviews,
)
from src.db.schema import create_schema


@pytest.fixture()
def db(tmp_path):
    database_path = tmp_path / "researchpilot_phase1.sqlite"
    connection = connect(database_path)
    create_schema(connection)
    try:
        yield connection
    finally:
        connection.close()


def create_supervisor(db, email, name):
    user = create_user(db, email=email, role="supervisor", display_name=name)
    supervisor = create_supervisor_profile(db, user_id=user["user_id"], department="Computing", title="Dr.")
    return user, supervisor


def test_schema_creates_expected_tables_with_foreign_keys_enabled(db):
    tables = {
        row["name"]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE ?",
            ("table", "sqlite_%"),
        )
    }

    assert {
        "users",
        "supervisor_profiles",
        "students",
        "supervisor_student_assignments",
        "proposals",
        "proposal_versions",
        "analyses",
        "supervisor_reviews",
        "ai_supervisor_review_drafts",
        "supervisor_review_drafts",
        "notification_logs",
    }.issubset(tables)
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_schema_adds_review_draft_tables_to_existing_database(tmp_path):
    database_path = tmp_path / "existing.sqlite"
    connection = connect(database_path)
    create_schema(connection)
    connection.execute("DROP TABLE supervisor_review_drafts")
    connection.execute("DROP TABLE ai_supervisor_review_drafts")
    connection.commit()
    connection.close()

    migrated = connect(database_path)
    create_schema(migrated)
    try:
        tables = {
            row["name"]
            for row in migrated.execute(
                "SELECT name FROM sqlite_master WHERE type = ? AND name NOT LIKE ?",
                ("table", "sqlite_%"),
            )
        }
        assert "ai_supervisor_review_drafts" in tables
        assert "supervisor_review_drafts" in tables
    finally:
        migrated.close()


def test_user_supervisor_and_student_repositories(db):
    user, supervisor = create_supervisor(db, "supervisor@example.test", "Supervisor A")
    student = create_student(
        db,
        academic_student_id="IT22101624",
        full_name="Student A",
        email="student@example.test",
        program="IT",
        cohort="2022",
    )

    assert get_user(db, user["user_id"])["email"] == "supervisor@example.test"
    assert supervisor["user_id"] == user["user_id"]
    assert get_student_by_academic_id(db, "IT22101624")["student_id"] == student["student_id"]
    assert student["student_id"] != student["academic_student_id"]


def test_supervisor_ownership_queries_do_not_leak_students(db):
    _, supervisor_a = create_supervisor(db, "supervisor-a@example.test", "Supervisor A")
    _, supervisor_b = create_supervisor(db, "supervisor-b@example.test", "Supervisor B")
    student_a = create_student(db, academic_student_id="ITA", full_name="Student A")
    student_b = create_student(db, academic_student_id="ITB", full_name="Student B")

    assign_supervisor_to_student(
        db,
        supervisor_id=supervisor_a["supervisor_id"],
        student_id=student_a["student_id"],
        assignment_role="primary_supervisor",
    )
    assign_supervisor_to_student(
        db,
        supervisor_id=supervisor_b["supervisor_id"],
        student_id=student_b["student_id"],
        assignment_role="primary_supervisor",
    )
    assign_supervisor_to_student(
        db,
        supervisor_id=supervisor_b["supervisor_id"],
        student_id=student_a["student_id"],
        assignment_role="co_supervisor",
    )

    supervisor_a_students = get_supervisor_students(db, supervisor_a["supervisor_id"])
    supervisor_b_students = get_supervisor_students(db, supervisor_b["supervisor_id"])
    student_a_supervisors = get_student_supervisors(db, student_a["student_id"])

    assert [student["student_id"] for student in supervisor_a_students] == [student_a["student_id"]]
    assert {student["student_id"] for student in supervisor_b_students} == {
        student_a["student_id"],
        student_b["student_id"],
    }
    assert {supervisor["assignment_role"] for supervisor in student_a_supervisors} == {
        "primary_supervisor",
        "co_supervisor",
    }


def test_duplicate_active_primary_supervisor_is_rejected(db):
    _, supervisor_a = create_supervisor(db, "primary-a@example.test", "Primary A")
    _, supervisor_b = create_supervisor(db, "primary-b@example.test", "Primary B")
    student = create_student(db, academic_student_id="ITPRIMARY", full_name="Primary Student")

    assign_supervisor_to_student(
        db,
        supervisor_id=supervisor_a["supervisor_id"],
        student_id=student["student_id"],
        assignment_role="primary_supervisor",
    )

    with pytest.raises(sqlite3.IntegrityError):
        assign_supervisor_to_student(
            db,
            supervisor_id=supervisor_b["supervisor_id"],
            student_id=student["student_id"],
            assignment_role="primary_supervisor",
        )


def test_proposal_versions_keep_same_filename_as_separate_versions(db):
    student = create_student(db, academic_student_id="ITVERSION", full_name="Version Student")
    proposal = create_proposal(db, student_id=student["student_id"], title="Proposal P001")
    version_1 = create_proposal_version(
        db,
        proposal_id=proposal["proposal_id"],
        version_number=1,
        original_filename="proposal.pdf",
        extracted_text="Version 1 text",
        status="SUBMITTED",
    )
    version_2 = create_proposal_version(
        db,
        proposal_id=proposal["proposal_id"],
        version_number=2,
        original_filename="proposal.pdf",
        extracted_text="Version 2 text",
        status="RESUBMITTED",
    )

    versions = get_proposal_versions(db, proposal["proposal_id"])
    proposals = get_student_proposals(db, student["student_id"])

    assert [version["version_number"] for version in versions] == [1, 2]
    assert version_1["version_id"] != version_2["version_id"]
    assert version_1["original_filename"] == version_2["original_filename"] == "proposal.pdf"
    assert get_proposal_version(db, version_1["version_id"])["extracted_text"] == "Version 1 text"
    assert get_proposal_version(db, version_2["version_id"])["extracted_text"] == "Version 2 text"
    assert proposals[0]["proposal_id"] == proposal["proposal_id"]


def test_analysis_links_to_correct_proposal_version_only(db):
    student = create_student(db, academic_student_id="ITANALYSIS", full_name="Analysis Student")
    proposal = create_proposal(db, student_id=student["student_id"], title="Analysis Proposal")
    version_1 = create_proposal_version(db, proposal_id=proposal["proposal_id"], version_number=1)
    version_2 = create_proposal_version(db, proposal_id=proposal["proposal_id"], version_number=2)

    analysis_1 = create_analysis(
        db,
        proposal_id=proposal["proposal_id"],
        version_id=version_1["version_id"],
        request_id="request-v1",
        source="pdf",
        input_text_snapshot="V1 analysis text",
    )
    analysis_2 = create_analysis(
        db,
        proposal_id=proposal["proposal_id"],
        version_id=version_2["version_id"],
        request_id="request-v2",
        source="pdf",
        input_text_snapshot="V2 analysis text",
    )

    assert [item["analysis_id"] for item in get_version_analyses(db, version_1["version_id"])] == [
        analysis_1["analysis_id"]
    ]
    assert [item["analysis_id"] for item in get_version_analyses(db, version_2["version_id"])] == [
        analysis_2["analysis_id"]
    ]


def test_cross_proposal_analysis_linking_is_rejected(db):
    student = create_student(db, academic_student_id="ITCROSS", full_name="Cross Student")
    proposal_a = create_proposal(db, student_id=student["student_id"], title="Proposal A")
    proposal_b = create_proposal(db, student_id=student["student_id"], title="Proposal B")
    version_a = create_proposal_version(db, proposal_id=proposal_a["proposal_id"], version_number=1)

    with pytest.raises(ValueError):
        create_analysis(
            db,
            proposal_id=proposal_b["proposal_id"],
            version_id=version_a["version_id"],
            request_id="bad-link",
        )


def test_supervisor_reviews_remain_linked_to_their_versions(db):
    _, supervisor = create_supervisor(db, "reviewer@example.test", "Reviewer")
    student = create_student(db, academic_student_id="ITREVIEW", full_name="Review Student")
    proposal = create_proposal(db, student_id=student["student_id"], title="Review Proposal")
    version_1 = create_proposal_version(db, proposal_id=proposal["proposal_id"], version_number=1)
    version_2 = create_proposal_version(db, proposal_id=proposal["proposal_id"], version_number=2)

    review_1 = create_supervisor_review(
        db,
        proposal_id=proposal["proposal_id"],
        version_id=version_1["version_id"],
        supervisor_id=supervisor["supervisor_id"],
        decision="REVISION_REQUESTED",
        overall_comment="Please revise methodology.",
    )
    review_2 = create_supervisor_review(
        db,
        proposal_id=proposal["proposal_id"],
        version_id=version_2["version_id"],
        supervisor_id=supervisor["supervisor_id"],
        decision="SEND_FEEDBACK",
        overall_comment="Send feedback report.",
    )

    assert [review["review_id"] for review in get_version_reviews(db, version_1["version_id"])] == [
        review_1["review_id"]
    ]
    assert [review["review_id"] for review in get_version_reviews(db, version_2["version_id"])] == [
        review_2["review_id"]
    ]


def test_notification_log_links_without_sending_email(db):
    _, supervisor = create_supervisor(db, "notify-supervisor@example.test", "Notifier")
    student = create_student(
        db,
        academic_student_id="ITNOTIFY",
        full_name="Notify Student",
        email="student@example.test",
    )
    proposal = create_proposal(db, student_id=student["student_id"], title="Notification Proposal")
    version = create_proposal_version(db, proposal_id=proposal["proposal_id"], version_number=1)
    review = create_supervisor_review(
        db,
        proposal_id=proposal["proposal_id"],
        version_id=version["version_id"],
        supervisor_id=supervisor["supervisor_id"],
        decision="REVISION_REQUESTED",
    )

    notification = create_notification_log(
        db,
        student_id=student["student_id"],
        proposal_id=proposal["proposal_id"],
        version_id=version["version_id"],
        review_id=review["review_id"],
        recipient_email="student@example.test",
        notification_type="REVISION_REQUESTED",
        status="PENDING",
    )

    notifications = get_version_notifications(db, version["version_id"])

    assert notification["recipient_email"] == "student@example.test"
    assert notification["status"] == "PENDING"
    assert notification["sent_at"] is None
    assert notifications[0]["notification_id"] == notification["notification_id"]
