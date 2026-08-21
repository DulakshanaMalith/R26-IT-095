import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.auth import hash_password, verify_password
from src.api.database import get_db_connection
from src.api.routers import auth, supervisor
from src.db.connection import connect
from src.db.repositories import (
    assign_supervisor_to_student,
    create_analysis,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_user,
    get_supervisor_identity_by_email,
    get_user_by_email,
    save_current_supervisor_review,
)
from src.db.schema import create_schema


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "test-auth-secret")
    database_path = tmp_path / "auth.sqlite"
    setup_connection = connect(database_path)
    create_schema(setup_connection)
    setup_connection.close()

    app = FastAPI()
    app.include_router(supervisor.router)
    app.include_router(auth.router)

    def override_connection():
        return connect(database_path)

    app.dependency_overrides[get_db_connection] = override_connection
    return TestClient(app), database_path


def create_supervisor(database_path, *, email, name, password="CorrectHorse1!"):
    connection = connect(database_path)
    try:
        user = create_user(
            connection,
            email=email,
            role="supervisor",
            display_name=name,
            password_hash=hash_password(password),
        )
        profile = create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
        return user, profile
    finally:
        connection.close()


def create_assigned_student(database_path, supervisor_id, academic_id, name, role="primary_supervisor"):
    connection = connect(database_path)
    try:
        student = create_student(connection, academic_student_id=academic_id, full_name=name)
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_id,
            student_id=student["student_id"],
            assignment_role=role,
        )
        return student
    finally:
        connection.close()


def create_proposal_work_item(
    database_path,
    student_id,
    *,
    title,
    analysis_id=None,
    supervisor_id=None,
    decision=None,
):
    connection = connect(database_path)
    try:
        proposal = create_proposal(connection, student_id=student_id, title=title)
        version = create_proposal_version(
            connection,
            proposal_id=proposal["proposal_id"],
            version_number=1,
            original_filename=f"{title}.pdf",
            source_type="pdf",
            extracted_text="Proposal text",
        )
        if analysis_id:
            create_analysis(
                connection,
                proposal_id=proposal["proposal_id"],
                version_id=version["version_id"],
                analysis_id=analysis_id,
            )
        if supervisor_id and decision:
            save_current_supervisor_review(
                connection,
                proposal_id=proposal["proposal_id"],
                version_id=version["version_id"],
                supervisor_id=supervisor_id,
                decision=decision,
                overall_comment="Reviewed by supervisor.",
            )
        return proposal, version
    finally:
        connection.close()


def login(client, email="a@example.test", password="CorrectHorse1!"):
    return client.post("/auth/login", json={"email": email, "password": password})


def register(client, email="new@example.test", password="CorrectHorse1!", confirm_password="CorrectHorse1!", **extra):
    payload = {
        "full_name": "New Supervisor",
        "email": email,
        "password": password,
        "confirm_password": confirm_password,
        **extra,
    }
    return client.post("/auth/register", json=payload)


def test_dev_login_is_disabled_by_default(auth_client):
    client, _ = auth_client

    response = client.post("/auth/dev-login")

    assert response.status_code == 404
    assert client.get("/auth/me").status_code == 401


def test_enabled_dev_login_establishes_real_session_for_protected_routes(auth_client, monkeypatch):
    client, database_path = auth_client
    monkeypatch.setenv("APP_ENABLE_DEV_LOGIN", "true")
    monkeypatch.setenv("APP_DEV_SUPERVISOR_EMAIL", "dev@example.test")
    monkeypatch.setenv("APP_DEV_SUPERVISOR_NAME", "Dev Supervisor")

    response = client.post("/auth/dev-login")

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "dev@example.test"
    assert payload["name"] == "Dev Supervisor"
    assert payload["role"] == "supervisor"
    assert "researchpilot_session" in response.headers["set-cookie"]

    me = client.get("/auth/me")
    dashboard = client.get("/me/dashboard")
    students = client.get("/me/students")
    create_student_response = client.post(
        "/me/students",
        json={
            "academic_student_id": "ITDEV",
            "full_name": "Dev Student",
            "email": "dev.student@example.test",
        },
    )

    assert me.status_code == 200
    assert me.json()["supervisor_id"] == payload["supervisor_id"]
    assert dashboard.status_code == 200
    assert students.status_code == 200
    assert create_student_response.status_code == 201
    assert client.get("/me/students").json()[0]["academic_student_id"] == "ITDEV"

    connection = connect(database_path)
    try:
        stored_user = get_user_by_email(connection, "dev@example.test")
        assert stored_user["password_hash"] != ""
        assert stored_user["password_hash"].startswith("pbkdf2_sha256$")
    finally:
        connection.close()

    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert client.get("/me/students").status_code == 401


def test_successful_supervisor_registration_stores_hash_and_authenticates(auth_client):
    client, database_path = auth_client

    response = register(client, email=" New.Supervisor@Example.TEST ")

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "new.supervisor@example.test"
    assert payload["name"] == "New Supervisor"
    assert payload["role"] == "supervisor"
    assert payload["supervisor_id"]
    assert "password_hash" not in payload
    assert "researchpilot_session" in response.headers["set-cookie"]

    connection = connect(database_path)
    try:
        stored_user = get_user_by_email(connection, "new.supervisor@example.test")
        assert stored_user["password_hash"] != "CorrectHorse1!"
        assert stored_user["password_hash"].startswith("pbkdf2_sha256$")
        assert verify_password("CorrectHorse1!", stored_user["password_hash"])
        identity = get_supervisor_identity_by_email(connection, "new.supervisor@example.test")
        assert identity["supervisor_id"] == payload["supervisor_id"]
    finally:
        connection.close()

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["supervisor_id"] == payload["supervisor_id"]
    assert "password_hash" not in me.json()
    dashboard = client.get("/me/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["assigned_students"] == 0
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401
    assert login(client, email="new.supervisor@example.test").status_code == 200
    assert client.get("/auth/me").json()["supervisor_id"] == payload["supervisor_id"]


def test_duplicate_registration_is_rejected_without_overwrite(auth_client):
    client, database_path = auth_client
    create_supervisor(database_path, email="a@example.test", name="Supervisor A", password="CorrectHorse1!")

    response = register(client, email="A@example.test", full_name="Other Name")

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists."
    connection = connect(database_path)
    try:
        stored_user = get_user_by_email(connection, "a@example.test")
        assert stored_user["display_name"] == "Supervisor A"
        assert verify_password("CorrectHorse1!", stored_user["password_hash"])
    finally:
        connection.close()


def test_registration_password_confirmation_and_strength_are_validated(auth_client):
    client, _ = auth_client

    mismatch = register(client, confirm_password="DifferentHorse1!")
    short_password = register(client, email="short@example.test", password="Short1", confirm_password="Short1")
    no_number = register(client, email="letters@example.test", password="CorrectHorse", confirm_password="CorrectHorse")

    assert mismatch.status_code == 422
    assert mismatch.json()["detail"] == "Passwords do not match."
    assert short_password.status_code == 422
    assert short_password.json()["detail"] == "Password must be at least 8 characters."
    assert no_number.status_code == 422
    assert no_number.json()["detail"] == "Password must include at least one number."


def test_registration_cannot_create_admin_or_student_role(auth_client):
    client, database_path = auth_client

    response = register(client, email="role@example.test", role="admin", student_id="IT999")

    assert response.status_code == 201
    assert response.json()["role"] == "supervisor"
    connection = connect(database_path)
    try:
        stored_user = get_user_by_email(connection, "role@example.test")
        assert stored_user["role"] == "supervisor"
        students = connection.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
        assert students == 0
    finally:
        connection.close()


def test_valid_supervisor_login_and_me_do_not_return_password_hash(auth_client):
    client, database_path = auth_client
    _, profile = create_supervisor(database_path, email="a@example.test", name="Supervisor A")

    response = login(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["supervisor_id"] == profile["supervisor_id"]
    assert payload["email"] == "a@example.test"
    assert payload["name"] == "Supervisor A"
    assert "password_hash" not in payload
    assert "researchpilot_session" in response.headers["set-cookie"]
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["supervisor_id"] == profile["supervisor_id"]
    assert "password_hash" not in me.json()


def test_invalid_password_and_unknown_email_are_rejected(auth_client):
    client, database_path = auth_client
    create_supervisor(database_path, email="a@example.test", name="Supervisor A")

    assert login(client, password="wrong").status_code == 401
    assert login(client, email="missing@example.test").status_code == 401


def test_me_unauthenticated_and_logout(auth_client):
    client, database_path = auth_client
    create_supervisor(database_path, email="a@example.test", name="Supervisor A")

    assert client.get("/auth/me").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_current_supervisor_students_are_protected_and_scoped(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    _, supervisor_b = create_supervisor(database_path, email="b@example.test", name="Supervisor B")
    student_a = create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITA", "Student A")
    create_assigned_student(database_path, supervisor_b["supervisor_id"], "ITB", "Student B")

    assert client.get("/me/students").status_code == 401
    assert login(client).status_code == 200

    payload = client.get("/me/students").json()
    assert [student["student_id"] for student in payload] == [student_a["student_id"]]


def test_current_supervisor_dashboard_is_protected_scoped_and_spoof_resistant(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    _, supervisor_b = create_supervisor(database_path, email="b@example.test", name="Supervisor B")
    student_a_analyzed = create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITA1", "Student A One")
    student_a_waiting = create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITA2", "Student A Two")
    create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITA3", "Student A Three")
    student_b = create_assigned_student(database_path, supervisor_b["supervisor_id"], "ITB1", "Student B One")

    create_proposal_work_item(
        database_path,
        student_a_analyzed["student_id"],
        title="A Analyzed Proposal",
        analysis_id="analysis-a",
        supervisor_id=supervisor_a["supervisor_id"],
        decision="REVISION_REQUESTED",
    )
    create_proposal_work_item(
        database_path,
        student_a_waiting["student_id"],
        title="A Waiting Proposal",
    )
    create_proposal_work_item(
        database_path,
        student_b["student_id"],
        title="B Private Proposal",
        analysis_id="analysis-b",
        supervisor_id=supervisor_b["supervisor_id"],
        decision="REVIEWED",
    )

    assert client.get("/me/dashboard").status_code == 401
    assert login(client, email="a@example.test").status_code == 200

    response = client.get(f"/me/dashboard?supervisor_id={supervisor_b['supervisor_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["assigned_students"] == 3
    assert payload["with_proposals"] == 2
    assert payload["analyzed_current_versions"] == 1
    assert payload["waiting_for_analysis"] == 1
    assert payload["revision_requested"] == 1
    assert payload["reviewed"] == 1
    titles = {item["proposal_title"] for item in payload["recent_proposals"]}
    assert titles == {"A Analyzed Proposal", "A Waiting Proposal"}
    assert "B Private Proposal" not in titles


def test_current_supervisor_dashboard_includes_co_supervised_students(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    _, supervisor_b = create_supervisor(database_path, email="b@example.test", name="Supervisor B")
    student_a = create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITCO", "Co Supervised Student")

    connection = connect(database_path)
    try:
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_b["supervisor_id"],
            student_id=student_a["student_id"],
            assignment_role="co_supervisor",
        )
    finally:
        connection.close()
    create_proposal_work_item(database_path, student_a["student_id"], title="Shared Proposal", analysis_id="shared-analysis")

    assert login(client, email="b@example.test").status_code == 200
    payload = client.get("/me/dashboard").json()

    assert payload["assigned_students"] == 1
    assert payload["with_proposals"] == 1
    assert payload["analyzed_current_versions"] == 1
    assert payload["recent_proposals"][0]["proposal_title"] == "Shared Proposal"


def test_co_supervisor_behavior_is_preserved(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    _, supervisor_b = create_supervisor(database_path, email="b@example.test", name="Supervisor B")
    student_a = create_assigned_student(database_path, supervisor_a["supervisor_id"], "ITA", "Student A")

    connection = connect(database_path)
    try:
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_b["supervisor_id"],
            student_id=student_a["student_id"],
            assignment_role="co_supervisor",
        )
    finally:
        connection.close()

    assert login(client, email="b@example.test").status_code == 200
    payload = client.get("/me/students").json()
    assert [student["student_id"] for student in payload] == [student_a["student_id"]]


def test_create_current_supervisor_student_assigns_to_authenticated_supervisor(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    assert client.post(
        "/me/students",
        json={"academic_student_id": "ITUNAUTH", "full_name": "Unauth Student"},
    ).status_code == 401
    assert login(client).status_code == 200

    response = client.post(
        "/me/students",
        json={
            "academic_student_id": "ITNEW",
            "full_name": "New Student",
            "email": "new@example.test",
            "program": "IT",
            "cohort": "2022",
        },
    )

    assert response.status_code == 201
    students = client.get("/me/students").json()
    assert [student["academic_student_id"] for student in students] == ["ITNEW"]
    legacy = client.get(f"/supervisors/{supervisor_a['supervisor_id']}/students").json()
    assert [student["academic_student_id"] for student in legacy] == ["ITNEW"]


def test_create_current_supervisor_student_rejects_duplicate_academic_id(auth_client):
    client, database_path = auth_client
    create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    assert login(client).status_code == 200

    first_response = client.post(
        "/me/students",
        json={"academic_student_id": "ITDUP", "full_name": "First Student"},
    )
    duplicate_response = client.post(
        "/me/students",
        json={"academic_student_id": "ITDUP", "full_name": "Duplicate Student"},
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "A student with this academic student ID already exists."
    students = client.get("/me/students").json()
    assert [student["academic_student_id"] for student in students] == ["ITDUP"]


def test_spoofed_supervisor_id_cannot_authorize_authenticated_review(auth_client):
    client, database_path = auth_client
    _, supervisor_a = create_supervisor(database_path, email="a@example.test", name="Supervisor A")
    _, supervisor_b = create_supervisor(database_path, email="b@example.test", name="Supervisor B")
    student_b = create_assigned_student(database_path, supervisor_b["supervisor_id"], "ITB", "Student B")

    connection = connect(database_path)
    try:
        proposal = create_proposal(connection, student_id=student_b["student_id"], title="B Proposal")
        version = create_proposal_version(connection, proposal_id=proposal["proposal_id"], version_number=1)
        create_analysis(
            connection,
            proposal_id=proposal["proposal_id"],
            version_id=version["version_id"],
            analysis_id="A-B",
        )
    finally:
        connection.close()

    assert login(client, email="a@example.test").status_code == 200
    response = client.post(
        f"/versions/{version['version_id']}/my-supervisor-review",
        json={
            "supervisor_id": supervisor_b["supervisor_id"],
            "decision": "READY_FOR_PANEL",
            "comments": "Trying to spoof B.",
        },
    )

    assert response.status_code == 403
    assert supervisor_a["supervisor_id"] != supervisor_b["supervisor_id"]
