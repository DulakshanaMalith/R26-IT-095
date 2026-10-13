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
from src.core import knowledge_graph
from tests.postgres_fixtures import connect
from src.db.repositories import (
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_user,
    get_version_analyses,
)
from src.db.history_repositories import list_analysis_history, list_grading_history, list_graph_history
from tests.postgres_fixtures import create_schema


COMPLETE_PROPOSAL_TEXT = (
    "Abstract This research investigates proposal quality and supervisor feedback in academic institutions. "
    "Introduction This study explains the research context and why proposal assessment needs structured support. "
    "Objectives The objectives are to evaluate completeness, feedback usefulness, and version-level improvement. "
    "Research Gap Existing systems lack reliable supervisor-centered version tracking for research proposal review. "
    "Methodology This study uses document analysis, prototype implementation, and supervisor evaluation procedures. "
    "Literature Review Previous studies discuss academic writing feedback, proposal assessment, and learning analytics. "
    "Evaluation The evaluation measures accuracy, usability, completeness detection, and supervisor review outcomes. "
    "References Smith and Perera describe research methods, educational technology, and academic assessment."
)

POOR_VALID_PROPOSAL_TEXT = (
    "Abstract This research study explores proposal feedback for students and supervisors in academic project review. "
    "Introduction The project is a research proposal about academic support, educational technology, and structured assessment. "
    "Objectives The objectives are to improve feedback quality, identify weak proposal sections, and support student revision. "
    "Research Gap Existing systems lack version-aware feedback links, clear evidence, and supervisor-centered academic workflows. "
    "Methodology The method uses document analysis, prototype implementation, data collection, survey feedback, and supervisor review. "
    "References Prior studies discuss educational systems, research methods, learning analytics, academic writing, and assessment."
)

INVALID_TEXT = "AWS EC2 lab notes. Create an instance, configure security groups, and ping the server."


class FakeWeaknessModel:
    def predict(self, values):
        return ["Weakness" if "version one" in values[0].lower() else "Strength"]


@pytest.fixture()
def version_analysis_client(tmp_path, monkeypatch):
    database_path = tmp_path / "phase3.postgresql"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    monkeypatch.setattr(core_logic, "DATA_DIR", history_dir)
    monkeypatch.setattr(knowledge_graph, "DATA_DIR", history_dir)
    monkeypatch.setattr(core_logic, "retrieve_feedback", lambda text, top_k=3: [{"comment_text": "Improve clarity.", "tag": "Weakness"}])
    monkeypatch.setattr(
        core_logic,
        "get_recommended_resources",
        lambda text, feedback="", top_k=3, missing_sections=None: [
            {
                "id": "methods-guide",
                "title": "Research Methods Guide",
                "description": "Guidance for choosing a suitable academic research method.",
                "url": "https://example.test/research-methods",
                "category": "Methodology",
                "reason": "The proposal needs stronger method design.",
                "relevance_score": 0.85,
            }
        ],
    )
    monkeypatch.setattr(core_logic, "grade_report_text", lambda text: 31.0)
    monkeypatch.setattr(
        core_logic,
        "analyze_knowledge_graph",
        lambda text: {"concepts": ["proposal"], "edges": [], "missing_concepts": []},
    )

    setup_connection = connect(database_path)
    create_schema(setup_connection)
    setup_connection.close()

    app = FastAPI()
    app.state.weakness_model = FakeWeaknessModel()
    app.include_router(supervisor.router)

    def override_connection():
        return connect(database_path)

    app.dependency_overrides[get_db_connection] = override_connection
    return TestClient(app), database_path, history_dir


def create_student_proposal_with_versions(database_path, version_texts):
    connection = connect(database_path)
    try:
        user = create_user(connection, email="phase3-supervisor@example.test", role="supervisor", display_name="Phase 3 Supervisor")
        create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
        student = create_student(
            connection,
            academic_student_id="ITPHASE3",
            full_name="Phase Three Student",
            email="phase3-student@example.test",
        )
        proposal = create_proposal(connection, student_id=student["student_id"], title="Versioned Proposal")
        versions = [
            create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=index,
                original_filename="proposal.pdf",
                source_type="pdf",
                extracted_text=text,
            )
            for index, text in enumerate(version_texts, start=1)
        ]
        return student, proposal, versions
    finally:
        connection.close()


def read_history(history_dir, filename):
    if filename == "analysis_history.json":
        return list_analysis_history()
    if filename == "grading_history.json":
        return list_grading_history()
    if filename == "knowledge_graph_history.json":
        return list_graph_history()
    return []


def test_good_version_analysis_creates_postgresql_link_and_history(version_analysis_client):
    client, database_path, history_dir = version_analysis_client
    _, proposal, versions = create_student_proposal_with_versions(database_path, [COMPLETE_PROPOSAL_TEXT])

    response = client.post(f"/versions/{versions[0]['version_id']}/analyze")

    assert response.status_code == 201
    payload = response.json()
    assert payload["proposal_id"] == proposal["proposal_id"]
    assert payload["version_id"] == versions[0]["version_id"]
    assert payload["version_number"] == 1
    assert payload["analysis_id"] == payload["analysis"]["analysis_id"]
    assert payload["analysis_id"] == payload["semantic_grade"]["analysis_id"]
    assert payload["knowledge_graph"]["analysis_id"] == payload["analysis_id"]
    assert payload["semantic_grade"]["final_readiness_percentage"] is not None
    assert payload["analysis"]["recommended_resources"] == [
        {
            "id": "methods-guide",
            "title": "Research Methods Guide",
            "description": "Guidance for choosing a suitable academic research method.",
            "url": "https://example.test/research-methods",
            "category": "Methodology",
            "reason": "The proposal needs stronger method design.",
            "relevance_score": 0.85,
        }
    ]

    connection = connect(database_path)
    try:
        linked = get_version_analyses(connection, versions[0]["version_id"])
        assert [item["analysis_id"] for item in linked] == [payload["analysis_id"]]
        assert linked[0]["proposal_id"] == proposal["proposal_id"]
        assert linked[0]["input_text_snapshot"] == COMPLETE_PROPOSAL_TEXT
    finally:
        connection.close()

    analysis_history = read_history(history_dir, "analysis_history.json")
    assert [item["analysis_id"] for item in analysis_history] == [payload["analysis_id"]]
    assert analysis_history[0]["recommended_resources"] == payload["analysis"]["recommended_resources"]
    assert [item["analysis_id"] for item in read_history(history_dir, "grading_history.json")] == [payload["analysis_id"]]
    assert [item["analysis_id"] for item in read_history(history_dir, "knowledge_graph_history.json")] == [payload["analysis_id"]]


def test_invalid_version_text_is_rejected_without_postgresql_link(version_analysis_client):
    client, database_path, history_dir = version_analysis_client
    _, _, versions = create_student_proposal_with_versions(database_path, [INVALID_TEXT])

    response = client.post(f"/versions/{versions[0]['version_id']}/analyze")

    assert response.status_code == 422
    assert "research proposal" in response.json()["detail"]["message"]
    connection = connect(database_path)
    try:
        assert get_version_analyses(connection, versions[0]["version_id"]) == []
    finally:
        connection.close()
    assert read_history(history_dir, "analysis_history.json") == []
    assert read_history(history_dir, "grading_history.json") == []


def test_poor_but_valid_proposal_analysis_preserves_readiness_outputs(version_analysis_client):
    client, database_path, _ = version_analysis_client
    _, proposal, versions = create_student_proposal_with_versions(database_path, [POOR_VALID_PROPOSAL_TEXT])

    response = client.post(f"/versions/{versions[0]['version_id']}/analyze")

    assert response.status_code == 201
    payload = response.json()
    assert payload["proposal_id"] == proposal["proposal_id"]
    assert payload["semantic_grade"]["proposal_completeness"]["percentage"] < 100
    assert payload["semantic_grade"]["final_readiness_percentage"] is not None


def test_same_filename_v1_v2_analysis_ids_do_not_mix(version_analysis_client):
    client, database_path, _ = version_analysis_client
    _, _, versions = create_student_proposal_with_versions(
        database_path,
        [
            f"{COMPLETE_PROPOSAL_TEXT} Version one content focuses on baseline supervisor workflow.",
            f"{COMPLETE_PROPOSAL_TEXT} Improved version two content adds clearer evaluation planning.",
        ],
    )

    v1_response = client.post(f"/versions/{versions[0]['version_id']}/analyze")
    v2_response = client.post(f"/versions/{versions[1]['version_id']}/analyze")

    assert v1_response.status_code == 201
    assert v2_response.status_code == 201
    v1_id = v1_response.json()["analysis_id"]
    v2_id = v2_response.json()["analysis_id"]
    assert v1_id != v2_id

    v1_links = client.get(f"/versions/{versions[0]['version_id']}/analyses").json()
    v2_links = client.get(f"/versions/{versions[1]['version_id']}/analyses").json()
    assert [item["analysis_id"] for item in v1_links] == [v1_id]
    assert [item["analysis_id"] for item in v2_links] == [v2_id]
    assert "version one content" in v1_links[0]["input_text_snapshot"].lower()
    assert "version two content" in v2_links[0]["input_text_snapshot"].lower()
    assert v1_links[0]["source"] == v2_links[0]["source"] == "pdf"


def test_multiple_analyses_on_same_version_are_unique_and_preserved(version_analysis_client):
    client, database_path, _ = version_analysis_client
    _, _, versions = create_student_proposal_with_versions(database_path, [COMPLETE_PROPOSAL_TEXT])

    first = client.post(f"/versions/{versions[0]['version_id']}/analyze").json()
    second = client.post(f"/versions/{versions[0]['version_id']}/analyze").json()

    assert first["analysis_id"] != second["analysis_id"]
    links = client.get(f"/versions/{versions[0]['version_id']}/analyses").json()
    assert [item["analysis_id"] for item in links] == [first["analysis_id"], second["analysis_id"]]


def test_version_not_found_returns_404(version_analysis_client):
    client, _, _ = version_analysis_client

    response = client.post("/versions/not-found/analyze")

    assert response.status_code == 404
