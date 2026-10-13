import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.database import get_db_connection
from src.api.routers import supervisor
from tests.postgres_fixtures import connect
from src.db.repositories import (
    assign_supervisor_to_student,
    create_ai_supervisor_review_draft,
    create_analysis,
    create_notification_log,
    create_proposal,
    create_proposal_version,
    create_supervisor_profile,
    create_supervisor_review,
    create_user,
    save_supervisor_review_draft,
)
from tests.postgres_fixtures import create_schema


@pytest.fixture()
def api_client(tmp_path):
    database_path = tmp_path / "researchpilot_phase2.postgresql"
    setup_connection = connect(database_path)
    create_schema(setup_connection)
    setup_connection.close()

    app = FastAPI()
    app.include_router(supervisor.router)

    def override_connection():
        return connect(database_path)

    app.dependency_overrides[get_db_connection] = override_connection
    return TestClient(app), database_path


def create_supervisor(database_path, email, name):
    connection = connect(database_path)
    try:
        user = create_user(connection, email=email, role="supervisor", display_name=name)
        return create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
    finally:
        connection.close()


def create_student(client, academic_id, full_name):
    response = client.post(
        "/students",
        json={
            "academic_student_id": academic_id,
            "full_name": full_name,
            "email": f"{academic_id.lower()}@example.test",
            "program": "IT",
            "cohort": "2022",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_supervisor_student_scoping_and_co_supervisor_support(api_client):
    client, database_path = api_client
    supervisor_a = create_supervisor(database_path, "supervisor-a@example.test", "Supervisor A")
    supervisor_b = create_supervisor(database_path, "supervisor-b@example.test", "Supervisor B")
    student_a = create_student(client, "ITA", "Student A")
    student_b = create_student(client, "ITB", "Student B")

    assert client.post(
        f"/supervisors/{supervisor_a['supervisor_id']}/students/{student_a['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201
    assert client.post(
        f"/supervisors/{supervisor_b['supervisor_id']}/students/{student_b['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201

    supervisor_a_students = client.get(f"/supervisors/{supervisor_a['supervisor_id']}/students").json()
    supervisor_b_students = client.get(f"/supervisors/{supervisor_b['supervisor_id']}/students").json()

    assert [student["student_id"] for student in supervisor_a_students] == [student_a["student_id"]]
    assert [student["student_id"] for student in supervisor_b_students] == [student_b["student_id"]]

    response = client.post(
        f"/supervisors/{supervisor_b['supervisor_id']}/students/{student_a['student_id']}/assign",
        json={"assignment_role": "co_supervisor"},
    )
    assert response.status_code == 201

    supervisor_b_students = client.get(f"/supervisors/{supervisor_b['supervisor_id']}/students").json()
    assert {student["student_id"] for student in supervisor_b_students} == {
        student_a["student_id"],
        student_b["student_id"],
    }


def test_supervisor_students_endpoint_uses_request_scoped_postgresql_connection(api_client):
    client, database_path = api_client
    supervisor = create_supervisor(database_path, "threaded-supervisor@example.test", "Threaded Supervisor")
    student = create_student(client, "ITTHREAD", "Threaded Student")
    assert client.post(
        f"/supervisors/{supervisor['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201

    connection = connect(database_path)
    try:
        proposal = create_proposal(connection, student_id=student["student_id"], title="Threaded Proposal")
        version = create_proposal_version(
            connection,
            proposal_id=proposal["proposal_id"],
            version_number=1,
            original_filename="proposal.pdf",
            source_type="pdf",
            extracted_text="Version text",
        )
    finally:
        connection.close()

    students_response = client.get(f"/supervisors/{supervisor['supervisor_id']}/students")
    proposals_response = client.get(f"/students/{student['student_id']}/proposals")
    versions_response = client.get(f"/proposals/{proposal['proposal_id']}/versions")

    assert students_response.status_code == 200
    assert students_response.json()[0]["student_id"] == student["student_id"]
    assert proposals_response.status_code == 200
    assert proposals_response.json()[0]["proposal_id"] == proposal["proposal_id"]
    assert versions_response.status_code == 200
    assert versions_response.json()[0]["version_id"] == version["version_id"]


def test_remove_student_deactivates_supervisor_assignment_only(api_client):
    client, database_path = api_client
    supervisor_profile = create_supervisor(database_path, "remove-basic@example.test", "Remove Basic")
    student = create_student(client, "ITREMOVE", "Remove Student")
    assert client.post(
        f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201

    response = client.delete(f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}")

    assert response.status_code == 200
    assert response.json()["active"] == 0
    assert client.get(f"/supervisors/{supervisor_profile['supervisor_id']}/students").json() == []
    assert count_rows(database_path, "students", "student_id = ?", (student["student_id"],)) == 1
    assert count_rows(
        database_path,
        "supervisor_student_assignments",
        "supervisor_id = ? AND student_id = ? AND active = 0",
        (supervisor_profile["supervisor_id"], student["student_id"]),
    ) == 1


def test_remove_student_preserves_co_supervisor_assignment(api_client):
    client, database_path = api_client
    supervisor_a = create_supervisor(database_path, "remove-a@example.test", "Remove A")
    supervisor_b = create_supervisor(database_path, "remove-b@example.test", "Remove B")
    student = create_student(client, "ITCOSAFE", "Shared Student")
    assert client.post(
        f"/supervisors/{supervisor_a['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201
    assert client.post(
        f"/supervisors/{supervisor_b['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "co_supervisor"},
    ).status_code == 201

    response = client.delete(f"/supervisors/{supervisor_a['supervisor_id']}/students/{student['student_id']}")

    assert response.status_code == 200
    assert client.get(f"/supervisors/{supervisor_a['supervisor_id']}/students").json() == []
    supervisor_b_students = client.get(f"/supervisors/{supervisor_b['supervisor_id']}/students").json()
    assert [item["student_id"] for item in supervisor_b_students] == [student["student_id"]]
    assert count_rows(
        database_path,
        "supervisor_student_assignments",
        "supervisor_id = ? AND student_id = ? AND active = 1",
        (supervisor_b["supervisor_id"], student["student_id"]),
    ) == 1


def test_remove_student_preserves_proposal_version_analysis_and_review_data(api_client):
    client, database_path = api_client
    supervisor_profile, student, proposal, versions = create_deletable_proposal_fixture(database_path, version_count=2, analysis_count=2)
    before = {
        "students": count_rows(database_path, "students", "student_id = ?", (student["student_id"],)),
        "proposals": count_rows(database_path, "proposals", "proposal_id = ?", (proposal["proposal_id"],)),
        "proposal_versions": count_rows(database_path, "proposal_versions", "proposal_id = ?", (proposal["proposal_id"],)),
        "analyses": count_rows(database_path, "analyses", "proposal_id = ?", (proposal["proposal_id"],)),
        "ai_supervisor_review_drafts": count_rows(database_path, "ai_supervisor_review_drafts", "proposal_id = ?", (proposal["proposal_id"],)),
        "supervisor_review_drafts": count_rows(database_path, "supervisor_review_drafts"),
        "supervisor_reviews": count_rows(database_path, "supervisor_reviews", "proposal_id = ?", (proposal["proposal_id"],)),
        "notification_logs": count_rows(database_path, "notification_logs", "proposal_id = ?", (proposal["proposal_id"],)),
    }

    response = client.delete(f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}")

    assert response.status_code == 200
    assert count_rows(
        database_path,
        "supervisor_student_assignments",
        "supervisor_id = ? AND student_id = ? AND active = 1",
        (supervisor_profile["supervisor_id"], student["student_id"]),
    ) == 0
    after = {
        "students": count_rows(database_path, "students", "student_id = ?", (student["student_id"],)),
        "proposals": count_rows(database_path, "proposals", "proposal_id = ?", (proposal["proposal_id"],)),
        "proposal_versions": count_rows(database_path, "proposal_versions", "proposal_id = ?", (proposal["proposal_id"],)),
        "analyses": count_rows(database_path, "analyses", "proposal_id = ?", (proposal["proposal_id"],)),
        "ai_supervisor_review_drafts": count_rows(database_path, "ai_supervisor_review_drafts", "proposal_id = ?", (proposal["proposal_id"],)),
        "supervisor_review_drafts": count_rows(database_path, "supervisor_review_drafts"),
        "supervisor_reviews": count_rows(database_path, "supervisor_reviews", "proposal_id = ?", (proposal["proposal_id"],)),
        "notification_logs": count_rows(database_path, "notification_logs", "proposal_id = ?", (proposal["proposal_id"],)),
    }
    assert after == before
    assert len(versions) == 2


def test_remove_student_returns_404_for_nonexistent_assignment(api_client):
    client, database_path = api_client
    supervisor_profile = create_supervisor(database_path, "remove-missing@example.test", "Remove Missing")
    student = create_student(client, "ITNOREL", "No Relationship")

    response = client.delete(f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Supervisor/student assignment not found."


def test_remove_student_does_not_remove_another_supervisors_assignment(api_client):
    client, database_path = api_client
    assigned_supervisor = create_supervisor(database_path, "assigned-remove@example.test", "Assigned Remove")
    outsider = create_supervisor(database_path, "outsider-remove@example.test", "Outsider Remove")
    student = create_student(client, "ITOUTREMOVE", "Outsider Remove Student")
    assert client.post(
        f"/supervisors/{assigned_supervisor['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201

    response = client.delete(f"/supervisors/{outsider['supervisor_id']}/students/{student['student_id']}")

    assert response.status_code == 404
    assigned_students = client.get(f"/supervisors/{assigned_supervisor['supervisor_id']}/students").json()
    assert [item["student_id"] for item in assigned_students] == [student["student_id"]]


def test_removed_student_remains_absent_after_refresh(api_client):
    client, database_path = api_client
    supervisor_profile = create_supervisor(database_path, "remove-refresh@example.test", "Remove Refresh")
    student = create_student(client, "ITREFRESHREMOVE", "Refresh Remove Student")
    assert client.post(
        f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    ).status_code == 201
    assert client.delete(f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}").status_code == 200

    first_refresh = client.get(f"/supervisors/{supervisor_profile['supervisor_id']}/students")
    second_refresh = client.get(f"/supervisors/{supervisor_profile['supervisor_id']}/students")

    assert first_refresh.status_code == 200
    assert second_refresh.status_code == 200
    assert first_refresh.json() == []
    assert second_refresh.json() == []


def test_remove_then_readd_same_academic_id_reuses_student_record(api_client):
    client, database_path = api_client
    supervisor_profile = create_supervisor(database_path, "remove-readd@example.test", "Remove Readd")
    client.app.dependency_overrides[supervisor.get_current_supervisor] = lambda: supervisor_profile
    try:
        first_add = client.post(
            "/me/students",
            json={
                "academic_student_id": "ITREADD",
                "full_name": "Readd Student",
                "email": "readd@example.test",
                "program": "IT",
                "cohort": "2022",
            },
        )
        assert first_add.status_code == 201
        student = first_add.json()
        assert client.delete(f"/me/students/{student['student_id']}").status_code == 200

        second_add = client.post(
            "/me/students",
            json={
                "academic_student_id": "ITREADD",
                "full_name": "Readd Student",
                "email": "readd@example.test",
                "program": "IT",
                "cohort": "2022",
            },
        )
    finally:
        client.app.dependency_overrides.pop(supervisor.get_current_supervisor, None)

    assert second_add.status_code == 201
    assert second_add.json()["student_id"] == student["student_id"]
    assert count_rows(database_path, "students", "academic_student_id = ?", ("ITREADD",)) == 1
    assert count_rows(
        database_path,
        "supervisor_student_assignments",
        "supervisor_id = ? AND student_id = ? AND active = 1",
        (supervisor_profile["supervisor_id"], student["student_id"]),
    ) == 1


def test_supervisor_scoped_add_reuses_removed_student_record(api_client):
    client, database_path = api_client
    supervisor_profile = create_supervisor(database_path, "remove-readd-explicit@example.test", "Remove Readd Explicit")
    payload = {
        "academic_student_id": "ITREADDEXPLICIT",
        "full_name": "Readd Explicit Student",
        "email": "readd-explicit@example.test",
        "program": "IT",
        "cohort": "2022",
    }
    first_add = client.post(f"/supervisors/{supervisor_profile['supervisor_id']}/students", json=payload)
    assert first_add.status_code == 201
    student = first_add.json()
    assert client.delete(f"/supervisors/{supervisor_profile['supervisor_id']}/students/{student['student_id']}").status_code == 200

    second_add = client.post(f"/supervisors/{supervisor_profile['supervisor_id']}/students", json=payload)

    assert second_add.status_code == 201
    assert second_add.json()["student_id"] == student["student_id"]
    assert count_rows(database_path, "students", "academic_student_id = ?", ("ITREADDEXPLICIT",)) == 1
    assert count_rows(
        database_path,
        "supervisor_student_assignments",
        "supervisor_id = ? AND student_id = ? AND active = 1",
        (supervisor_profile["supervisor_id"], student["student_id"]),
    ) == 1


def test_student_proposals_versions_and_analyses_are_scoped(api_client):
    client, _ = api_client
    student_a = create_student(client, "ITPROPA", "Student A")
    student_b = create_student(client, "ITPROPB", "Student B")

    proposal_response = client.post(
        f"/students/{student_a['student_id']}/proposals",
        json={"title": "Proposal P1"},
    )
    assert proposal_response.status_code == 201
    proposal = proposal_response.json()

    student_a_proposals = client.get(f"/students/{student_a['student_id']}/proposals").json()
    student_b_proposals = client.get(f"/students/{student_b['student_id']}/proposals").json()
    assert [item["proposal_id"] for item in student_a_proposals] == [proposal["proposal_id"]]
    assert student_b_proposals == []

    version_1_response = client.post(
        f"/proposals/{proposal['proposal_id']}/versions",
        json={"original_filename": "proposal.pdf", "source_type": "pdf", "extracted_text": "Version 1"},
    )
    version_2_response = client.post(
        f"/proposals/{proposal['proposal_id']}/versions",
        json={"original_filename": "proposal.pdf", "source_type": "pdf", "extracted_text": "Version 2"},
    )
    assert version_1_response.status_code == 201
    assert version_2_response.status_code == 201
    version_1 = version_1_response.json()
    version_2 = version_2_response.json()

    assert version_1["version_number"] == 1
    assert version_2["version_number"] == 2
    assert version_1["version_id"] != version_2["version_id"]
    assert version_1["original_filename"] == version_2["original_filename"] == "proposal.pdf"

    versions = client.get(f"/proposals/{proposal['proposal_id']}/versions").json()
    assert [version["version_number"] for version in versions] == [1, 2]
    assert [version["version_id"] for version in versions] == [
        version_1["version_id"],
        version_2["version_id"],
    ]

    assert client.get(f"/versions/{version_1['version_id']}/analyses").json() == []
    assert client.get(f"/versions/{version_2['version_id']}/analyses").json() == []


def test_clear_errors_for_duplicates_and_unknown_resources(api_client):
    client, database_path = api_client
    supervisor = create_supervisor(database_path, "errors@example.test", "Errors")
    student = create_student(client, "ITERROR", "Error Student")

    duplicate_student = client.post(
        "/students",
        json={"academic_student_id": "ITERROR", "full_name": "Duplicate Student"},
    )
    assert duplicate_student.status_code == 409

    missing_student = client.get("/students/missing-student")
    assert missing_student.status_code == 404

    invalid_role = client.post(
        f"/supervisors/{supervisor['supervisor_id']}/students/{student['student_id']}/assign",
        json={"assignment_role": "external_marker"},
    )
    assert invalid_role.status_code == 422

    unknown_supervisor = client.post(
        f"/supervisors/missing-supervisor/students/{student['student_id']}/assign",
        json={"assignment_role": "primary_supervisor"},
    )
    assert unknown_supervisor.status_code == 404


def count_rows(database_path, table, where="", params=()):
    connection = connect(database_path)
    try:
        suffix = f" WHERE {where}" if where else ""
        return connection.execute(f"SELECT COUNT(*) FROM {table}{suffix}", params).fetchone()[0]
    finally:
        connection.close()


def create_deletable_proposal_fixture(database_path, *, version_count=1, analysis_count=1):
    connection = connect(database_path)
    try:
        supervisor = create_supervisor_profile(
            connection,
            user_id=create_user(
                connection,
                email=f"delete-{version_count}-{analysis_count}@example.test",
                role="supervisor",
                display_name="Delete Supervisor",
            )["user_id"],
            department="Computing",
            title="Dr.",
        )
        student = create_student_record(connection, f"ITDEL{version_count}{analysis_count}")
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor["supervisor_id"],
            student_id=student["student_id"],
            assignment_role="primary_supervisor",
        )
        proposal = create_proposal(connection, student_id=student["student_id"], title="Delete Me")
        versions = []
        for version_number in range(1, version_count + 1):
            version = create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=version_number,
                original_filename=f"delete-v{version_number}.pdf",
                source_type="pdf",
                extracted_text=f"Version {version_number} text",
            )
            versions.append(version)
            for analysis_index in range(1, analysis_count + 1):
                analysis_id = f"A{version_number}{analysis_index}"
                create_analysis(
                    connection,
                    proposal_id=proposal["proposal_id"],
                    version_id=version["version_id"],
                    analysis_id=analysis_id,
                    request_id=analysis_id,
                    source="pdf",
                    input_text_snapshot=f"Analysis {analysis_id}",
                )
                create_ai_supervisor_review_draft(
                    connection,
                    proposal_id=proposal["proposal_id"],
                    version_id=version["version_id"],
                    analysis_id=analysis_id,
                    draft={
                        "overall_assessment": "Assessment",
                        "strengths": ["Strength"],
                        "areas_requiring_improvement": ["Improvement"],
                        "methodology_feedback": "Methodology",
                        "evaluation_validation_feedback": "Evaluation",
                        "recommendations": ["Recommendation"],
                        "suggested_revision_instructions": ["Revise"],
                    },
                )
                save_supervisor_review_draft(
                    connection,
                    version_id=version["version_id"],
                    analysis_id=analysis_id,
                    supervisor_id=supervisor["supervisor_id"],
                    ai_draft_id=connection.execute(
                        """
                        SELECT draft_id FROM ai_supervisor_review_drafts
                        WHERE version_id = ? AND analysis_id = ?
                        """,
                        (version["version_id"], analysis_id),
                    ).fetchone()["draft_id"],
                    overall_assessment="Edited assessment",
                    strengths=["Edited strength"],
                    areas_requiring_improvement=["Edited improvement"],
                    methodology_feedback="Edited methodology",
                    evaluation_validation_feedback="Edited evaluation",
                    recommendations=["Edited recommendation"],
                    suggested_revision_instructions=["Edited revision"],
                    supervisor_comments="Human comments",
                )
            review = create_supervisor_review(
                connection,
                proposal_id=proposal["proposal_id"],
                version_id=version["version_id"],
                supervisor_id=supervisor["supervisor_id"],
                decision="REVISION_REQUESTED",
                overall_comment="Revise this version.",
            )
            create_notification_log(
                connection,
                student_id=student["student_id"],
                proposal_id=proposal["proposal_id"],
                version_id=version["version_id"],
                review_id=review["review_id"],
                notification_type="REVISION_REQUESTED",
                status="CREATED",
            )
        return supervisor, student, proposal, versions
    finally:
        connection.close()


def create_student_record(connection, academic_id):
    from src.db.repositories import create_student as create_student_repo

    return create_student_repo(
        connection,
        academic_student_id=academic_id,
        full_name=f"{academic_id} Student",
        email=f"{academic_id.lower()}@example.test",
        program="IT",
        cohort="2022",
    )


def test_delete_proposal_removes_v1_workflow_records_but_preserves_student_and_assignment(api_client):
    client, database_path = api_client
    supervisor, student, proposal, _ = create_deletable_proposal_fixture(database_path)

    response = client.delete(
        f"/proposals/{proposal['proposal_id']}",
        params={"supervisor_id": supervisor["supervisor_id"]},
    )

    assert response.status_code == 200
    assert response.json()["deleted"]["proposals"] == 1
    assert count_rows(database_path, "students", "student_id = ?", (student["student_id"],)) == 1
    assert count_rows(database_path, "supervisor_student_assignments", "student_id = ?", (student["student_id"],)) == 1
    assert count_rows(database_path, "proposals", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "proposal_versions", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "analyses", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "supervisor_reviews", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "ai_supervisor_review_drafts", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "supervisor_review_drafts") == 0
    assert count_rows(database_path, "notification_logs", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert client.get(f"/students/{student['student_id']}/proposals").json() == []


def test_delete_proposal_removes_three_versions_and_analysis_links_without_orphans(api_client):
    client, database_path = api_client
    supervisor, student, proposal, _ = create_deletable_proposal_fixture(database_path, version_count=3, analysis_count=2)

    response = client.delete(
        f"/proposals/{proposal['proposal_id']}",
        params={"supervisor_id": supervisor["supervisor_id"]},
    )

    assert response.status_code == 200
    deleted = response.json()["deleted"]
    assert deleted["proposal_versions"] == 3
    assert deleted["analyses"] == 6
    assert deleted["supervisor_review_drafts"] == 6
    assert deleted["ai_supervisor_review_drafts"] == 6
    assert deleted["supervisor_reviews"] == 3
    assert deleted["notification_logs"] == 3
    assert count_rows(database_path, "students", "student_id = ?", (student["student_id"],)) == 1
    assert count_rows(database_path, "supervisor_student_assignments", "student_id = ?", (student["student_id"],)) == 1
    assert count_rows(database_path, "proposal_versions", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "analyses", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "supervisor_reviews", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "ai_supervisor_review_drafts", "proposal_id = ?", (proposal["proposal_id"],)) == 0
    assert count_rows(database_path, "supervisor_review_drafts") == 0
    assert count_rows(database_path, "notification_logs", "proposal_id = ?", (proposal["proposal_id"],)) == 0


def test_delete_missing_proposal_returns_404(api_client):
    client, database_path = api_client
    supervisor = create_supervisor(database_path, "missing-delete@example.test", "Missing Delete")

    response = client.delete("/proposals/missing-proposal", params={"supervisor_id": supervisor["supervisor_id"]})

    assert response.status_code == 404


def test_delete_proposal_rejects_unassigned_supervisor(api_client):
    client, database_path = api_client
    assigned_supervisor, _, proposal, _ = create_deletable_proposal_fixture(database_path)
    outsider = create_supervisor(database_path, "outsider-delete@example.test", "Outsider Delete")

    response = client.delete(
        f"/proposals/{proposal['proposal_id']}",
        params={"supervisor_id": outsider["supervisor_id"]},
    )

    assert response.status_code == 403
    assert count_rows(database_path, "proposals", "proposal_id = ?", (proposal["proposal_id"],)) == 1
    assert assigned_supervisor["supervisor_id"] != outsider["supervisor_id"]


def test_main_app_import_registers_existing_and_supervisor_routes():
    from src.api.main import app

    paths = set(app.openapi()["paths"])

    assert "/analyze" in paths
    assert "/grade-report" in paths
    assert "/supervisors/{supervisor_id}/students" in paths
    assert "/supervisors/{supervisor_id}/students/{student_id}" in paths
    assert "/me/students/{student_id}" in paths
    assert "/students" in paths
    assert "/versions/{version_id}/analyses" in paths
    assert "/versions/{version_id}/review-draft" in paths
    assert "/versions/{version_id}/supervisor-review-draft" in paths
    assert "/versions/{version_id}/review-outcome" in paths
    assert "/versions/{version_id}/supervisor-reviews" in paths
    assert "/proposals/{proposal_id}/revised-versions" in paths
