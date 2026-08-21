import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.database import get_db_connection
from src.api.routers import supervisor
from src.api.services import core_logic
from src.db.connection import connect
from src.db.repositories import (
    assign_supervisor_to_student,
    create_analysis,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_user,
    get_version_reviews,
)
from src.db.schema import create_schema


@pytest.fixture()
def review_client(tmp_path, monkeypatch):
    database_path = tmp_path / "supervisor_reviews.sqlite"
    monkeypatch.setattr(core_logic, "predict_tag", lambda *args, **kwargs: pytest.fail("review endpoint must not invoke models"))
    monkeypatch.setattr(core_logic, "grade_report_text", lambda *args, **kwargs: pytest.fail("review endpoint must not grade"))
    monkeypatch.setattr(core_logic, "retrieve_feedback", lambda *args, **kwargs: pytest.fail("review endpoint must not retrieve feedback"))

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


def create_review_fixture(database_path, *, analyzed=True, version_count=1, assign_role="primary_supervisor"):
    connection = connect(database_path)
    try:
        supervisor_profile = create_supervisor_profile(
            connection,
            user_id=create_user(
                connection,
                email="reviewer@example.test",
                role="supervisor",
                display_name="Review Supervisor",
            )["user_id"],
            department="Computing",
            title="Dr.",
        )
        student = create_student(connection, academic_student_id="ITREVIEWAPI", full_name="Review API Student")
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            student_id=student["student_id"],
            assignment_role=assign_role,
        )
        proposal = create_proposal(connection, student_id=student["student_id"], title="Review API Proposal")
        versions = [
            create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=index,
                original_filename="same-proposal.pdf",
                source_type="pdf",
                extracted_text=f"Version {index}",
            )
            for index in range(1, version_count + 1)
        ]
        if analyzed:
            for index, version in enumerate(versions, start=1):
                create_analysis(
                    connection,
                    proposal_id=proposal["proposal_id"],
                    version_id=version["version_id"],
                    analysis_id=f"A{index}",
                    request_id=f"A{index}",
                    source="pdf",
                    input_text_snapshot=f"Analyzed V{index}",
                )
        return supervisor_profile, student, proposal, versions
    finally:
        connection.close()


def post_review(client, version_id, supervisor_id, decision, comments="Supervisor comments."):
    return client.post(
        f"/versions/{version_id}/supervisor-reviews",
        json={"supervisor_id": supervisor_id, "decision": decision, "comments": comments},
    )


def test_analyzed_v1_request_revision_saves(review_client):
    client, database_path = review_client
    supervisor_profile, _, proposal, versions = create_review_fixture(database_path)

    response = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "REQUEST_REVISION")

    assert response.status_code == 201
    payload = response.json()
    assert payload["proposal_id"] == proposal["proposal_id"]
    assert payload["version_id"] == versions[0]["version_id"]
    assert payload["supervisor_id"] == supervisor_profile["supervisor_id"]
    assert payload["decision"] == "REQUEST_REVISION"


def test_analyzed_v1_ready_for_panel_saves(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path)

    response = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "READY_FOR_PANEL")

    assert response.status_code == 201
    assert response.json()["decision"] == "READY_FOR_PANEL"


def test_unanalyzed_v1_review_is_rejected(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path, analyzed=False)

    response = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "REQUEST_REVISION")

    assert response.status_code == 409
    assert response.json()["detail"] == "Analyze this proposal version before recording a supervisor decision."


def test_invalid_version_is_rejected(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, _ = create_review_fixture(database_path)

    response = post_review(client, "missing-version", supervisor_profile["supervisor_id"], "REQUEST_REVISION")

    assert response.status_code == 404


def test_invalid_supervisor_is_rejected(review_client):
    client, database_path = review_client
    _, _, _, versions = create_review_fixture(database_path)

    response = post_review(client, versions[0]["version_id"], "missing-supervisor", "REQUEST_REVISION")

    assert response.status_code == 404


def test_supervisor_not_assigned_to_student_is_rejected(review_client):
    client, database_path = review_client
    _, _, _, versions = create_review_fixture(database_path)
    outsider = create_supervisor(database_path, "outsider@example.test", "Outsider")

    response = post_review(client, versions[0]["version_id"], outsider["supervisor_id"], "REQUEST_REVISION")

    assert response.status_code == 403


def test_assigned_co_supervisor_is_allowed(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path, assign_role="co_supervisor")

    response = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "READY_FOR_PANEL")

    assert response.status_code == 201
    assert response.json()["supervisor_id"] == supervisor_profile["supervisor_id"]


def test_comments_persist_and_read_endpoint_returns_saved_review(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path)

    post_review(
        client,
        versions[0]["version_id"],
        supervisor_profile["supervisor_id"],
        "REQUEST_REVISION",
        comments="Clarify the research gap before panel review.",
    )
    payload = client.get(f"/versions/{versions[0]['version_id']}/supervisor-reviews").json()

    assert payload[0]["comments"] == "Clarify the research gap before panel review."
    assert payload[0]["decision"] == "REQUEST_REVISION"


def test_v1_and_v2_reviews_are_isolated_and_coexist(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path, version_count=2)

    v1 = post_review(
        client,
        versions[0]["version_id"],
        supervisor_profile["supervisor_id"],
        "REQUEST_REVISION",
        comments="Revise V1.",
    ).json()
    v2 = post_review(
        client,
        versions[1]["version_id"],
        supervisor_profile["supervisor_id"],
        "READY_FOR_PANEL",
        comments="V2 is ready.",
    ).json()

    assert v1["decision"] == "REQUEST_REVISION"
    assert v2["decision"] == "READY_FOR_PANEL"
    assert v1["review_id"] != v2["review_id"]
    assert client.get(f"/versions/{versions[0]['version_id']}/supervisor-reviews").json()[0]["decision"] == "REQUEST_REVISION"
    assert client.get(f"/versions/{versions[1]['version_id']}/supervisor-reviews").json()[0]["decision"] == "READY_FOR_PANEL"


def test_filename_does_not_determine_review_identity(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path, version_count=2)

    post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "REQUEST_REVISION")
    post_review(client, versions[1]["version_id"], supervisor_profile["supervisor_id"], "READY_FOR_PANEL")

    assert versions[0]["original_filename"] == versions[1]["original_filename"] == "same-proposal.pdf"
    assert client.get(f"/versions/{versions[0]['version_id']}/supervisor-reviews").json()[0]["version_id"] == versions[0]["version_id"]
    assert client.get(f"/versions/{versions[1]['version_id']}/supervisor-reviews").json()[0]["version_id"] == versions[1]["version_id"]


def test_invalid_decision_is_rejected(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path)

    response = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "AUTO_APPROVE")

    assert response.status_code == 422


def test_review_change_updates_current_review_for_same_supervisor_and_version(review_client):
    client, database_path = review_client
    supervisor_profile, _, _, versions = create_review_fixture(database_path)

    first = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "REQUEST_REVISION").json()
    second = post_review(client, versions[0]["version_id"], supervisor_profile["supervisor_id"], "READY_FOR_PANEL").json()

    assert first["review_id"] == second["review_id"]
    assert second["decision"] == "READY_FOR_PANEL"
    connection = connect(database_path)
    try:
        reviews = get_version_reviews(connection, versions[0]["version_id"])
        assert len(reviews) == 1
        assert reviews[0]["decision"] == "READY_FOR_PANEL"
    finally:
        connection.close()
