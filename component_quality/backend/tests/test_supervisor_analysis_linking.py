import json
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
    create_proposal,
    create_proposal_version,
    create_student,
    create_user,
    get_version_analyses,
)
from src.db.schema import create_schema


@pytest.fixture()
def link_client(tmp_path, monkeypatch):
    database_path = tmp_path / "analysis_linking.sqlite"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    analysis_history_path = history_dir / "analysis_history.json"
    grading_history_path = history_dir / "grading_history.json"
    analysis_history_path.write_text("[]", encoding="utf-8")
    grading_history_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(core_logic, "DATA_DIR", history_dir)
    monkeypatch.setattr(core_logic, "HISTORY_PATH", analysis_history_path)
    monkeypatch.setattr(core_logic, "GRADING_HISTORY_PATH", grading_history_path)
    monkeypatch.setattr(core_logic, "predict_tag", lambda *args, **kwargs: pytest.fail("link endpoint must not invoke models"))
    monkeypatch.setattr(core_logic, "grade_report_text", lambda *args, **kwargs: pytest.fail("link endpoint must not grade"))
    monkeypatch.setattr(core_logic, "analyze_knowledge_graph", lambda *args, **kwargs: pytest.fail("link endpoint must not build graphs"))

    setup_connection = connect(database_path)
    create_schema(setup_connection)
    setup_connection.close()

    app = FastAPI()
    app.include_router(supervisor.router)

    def override_connection():
        return connect(database_path)

    app.dependency_overrides[get_db_connection] = override_connection
    return TestClient(app), database_path, analysis_history_path


def create_versioned_proposal(database_path, *, filenames=("same-name.pdf",), texts=("Version one text",)):
    connection = connect(database_path)
    try:
        user = create_user(connection, email=f"{texts[0][:8]}@example.test", role="supervisor", display_name="Link Supervisor")
        student = create_student(
            connection,
            academic_student_id=f"IT{texts[0][:6].upper()}",
            full_name="Link Student",
        )
        proposal = create_proposal(connection, student_id=student["student_id"], title="Linked Proposal")
        versions = [
            create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=index,
                original_filename=filenames[index - 1] if index <= len(filenames) else filenames[-1],
                source_type="pdf",
                extracted_text=text,
            )
            for index, text in enumerate(texts, start=1)
        ]
        return proposal, versions
    finally:
        connection.close()


def write_analysis_history(path, records):
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def analysis_record(analysis_id, *, text="Completed proposal text", source="pdf"):
    return {
        "id": analysis_id,
        "analysis_id": analysis_id,
        "request_id": analysis_id,
        "source": source,
        "filename": "same-name.pdf",
        "input_text": text,
        "predicted_tag": "Strength",
        "retrieved_feedback": [],
        "recommended_resources": [],
    }


def test_valid_existing_analysis_id_links_to_v1(link_client):
    client, database_path, history_path = link_client
    proposal, versions = create_versioned_proposal(database_path)
    write_analysis_history(history_path, [analysis_record("A1", text="Saved Analyzer result")])

    response = client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["analysis_id"] == "A1"
    assert payload["proposal_id"] == proposal["proposal_id"]
    assert payload["version_id"] == versions[0]["version_id"]
    assert payload["input_text_snapshot"] == "Saved Analyzer result"


def test_linking_same_analysis_twice_is_idempotent(link_client):
    client, database_path, history_path = link_client
    _, versions = create_versioned_proposal(database_path)
    write_analysis_history(history_path, [analysis_record("A1")])

    first = client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"})
    second = client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"})

    assert first.status_code == 201
    assert second.status_code == 201
    connection = connect(database_path)
    try:
        links = get_version_analyses(connection, versions[0]["version_id"])
        assert [link["analysis_id"] for link in links] == ["A1"]
    finally:
        connection.close()


def test_invalid_version_id_is_rejected(link_client):
    client, _, history_path = link_client
    write_analysis_history(history_path, [analysis_record("A1")])

    response = client.post("/versions/missing-version/analyses/link", json={"analysis_id": "A1"})

    assert response.status_code == 404


def test_empty_analysis_id_is_rejected(link_client):
    client, database_path, _ = link_client
    _, versions = create_versioned_proposal(database_path)

    response = client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "   "})

    assert response.status_code == 422


def test_nonexistent_analysis_id_is_rejected(link_client):
    client, database_path, history_path = link_client
    _, versions = create_versioned_proposal(database_path)
    write_analysis_history(history_path, [])

    response = client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "MISSING"})

    assert response.status_code == 404


def test_v1_and_v2_links_remain_isolated_with_same_filename(link_client):
    client, database_path, history_path = link_client
    _, versions = create_versioned_proposal(
        database_path,
        filenames=("proposal.pdf", "proposal.pdf"),
        texts=("Version one text", "Version two text"),
    )
    write_analysis_history(history_path, [
        analysis_record("A1", text="Version one analyzed"),
        analysis_record("A2", text="Version two analyzed"),
    ])

    assert client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"}).status_code == 201
    assert client.post(f"/versions/{versions[1]['version_id']}/analyses/link", json={"analysis_id": "A2"}).status_code == 201

    v1_links = client.get(f"/versions/{versions[0]['version_id']}/analyses").json()
    v2_links = client.get(f"/versions/{versions[1]['version_id']}/analyses").json()
    assert [item["analysis_id"] for item in v1_links] == ["A1"]
    assert [item["analysis_id"] for item in v2_links] == ["A2"]
    assert v1_links[0]["input_text_snapshot"] == "Version one analyzed"
    assert v2_links[0]["input_text_snapshot"] == "Version two analyzed"


def test_same_analysis_id_cannot_be_linked_to_different_version(link_client):
    client, database_path, history_path = link_client
    _, versions = create_versioned_proposal(database_path, texts=("Version one text", "Version two text"))
    write_analysis_history(history_path, [analysis_record("A1")])

    assert client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"}).status_code == 201
    response = client.post(f"/versions/{versions[1]['version_id']}/analyses/link", json={"analysis_id": "A1"})

    assert response.status_code == 409


def test_multiple_unique_analysis_ids_may_link_to_same_version(link_client):
    client, database_path, history_path = link_client
    _, versions = create_versioned_proposal(database_path)
    write_analysis_history(history_path, [analysis_record("A1"), analysis_record("A2")])

    assert client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A1"}).status_code == 201
    assert client.post(f"/versions/{versions[0]['version_id']}/analyses/link", json={"analysis_id": "A2"}).status_code == 201

    links = client.get(f"/versions/{versions[0]['version_id']}/analyses").json()
    assert [item["analysis_id"] for item in links] == ["A1", "A2"]


def test_revised_proposal_creates_v2_and_links_a2_without_touching_v1(link_client):
    client, database_path, history_path = link_client
    proposal, versions = create_versioned_proposal(
        database_path,
        filenames=("proposal.pdf",),
        texts=("Original V1 extracted text",),
    )
    v1 = versions[0]
    write_analysis_history(history_path, [
        analysis_record("A1", text="Original V1 analyzed text"),
        analysis_record("A2", text="Revised V2 analyzed text"),
    ])

    assert client.post(f"/versions/{v1['version_id']}/analyses/link", json={"analysis_id": "A1"}).status_code == 201

    v2_response = client.post(
        f"/proposals/{proposal['proposal_id']}/versions",
        json={
            "original_filename": "proposal.pdf",
            "source_type": "pdf",
            "extracted_text": "Revised V2 extracted text",
        },
    )
    assert v2_response.status_code == 201
    v2 = v2_response.json()

    assert v2["proposal_id"] == proposal["proposal_id"]
    assert v2["version_number"] == 2
    assert v2["version_id"] != v1["version_id"]
    assert v2["original_filename"] == v1["original_filename"] == "proposal.pdf"
    assert v2["extracted_text"] == "Revised V2 extracted text"

    loaded_versions = client.get(f"/proposals/{proposal['proposal_id']}/versions").json()
    assert [version["version_number"] for version in loaded_versions] == [1, 2]
    assert loaded_versions[0]["version_id"] == v1["version_id"]
    assert loaded_versions[0]["extracted_text"] == "Original V1 extracted text"
    assert loaded_versions[1]["version_id"] == v2["version_id"]

    assert client.get(f"/versions/{v2['version_id']}/analyses").json() == []

    assert client.post(f"/versions/{v2['version_id']}/analyses/link", json={"analysis_id": "A2"}).status_code == 201
    assert client.post(f"/versions/{v2['version_id']}/analyses/link", json={"analysis_id": "A2"}).status_code == 201

    v1_links = client.get(f"/versions/{v1['version_id']}/analyses").json()
    v2_links = client.get(f"/versions/{v2['version_id']}/analyses").json()
    assert [item["analysis_id"] for item in v1_links] == ["A1"]
    assert [item["analysis_id"] for item in v2_links] == ["A2"]
