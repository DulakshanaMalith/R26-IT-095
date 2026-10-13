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
from src.api.services.improvement_tracking import select_best_available_version
from tests.postgres_fixtures import connect
from src.db.repositories import (
    create_analysis,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_supervisor_review,
    create_user,
)
from src.db.history_repositories import replace_analysis_history, replace_grading_history, replace_graph_history
from tests.postgres_fixtures import create_schema


@pytest.fixture()
def improvement_client(tmp_path, monkeypatch):
    database_path = tmp_path / "phase4.postgresql"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    monkeypatch.setattr(core_logic, "DATA_DIR", history_dir)
    monkeypatch.setattr(knowledge_graph, "DATA_DIR", history_dir)

    setup_connection = connect(database_path)
    create_schema(setup_connection)
    setup_connection.close()
    replace_analysis_history([])
    replace_grading_history([])
    replace_graph_history([])

    app = FastAPI()
    app.include_router(supervisor.router)

    def override_connection():
        return connect(database_path)

    app.dependency_overrides[get_db_connection] = override_connection
    return TestClient(app), database_path, history_dir


def write_history(history_dir, analysis_ids, grading_records):
    analysis_records = [
        {
            "id": analysis_id,
            "analysis_id": analysis_id,
            "request_id": analysis_id,
            "timestamp": f"2026-01-01T00:00:{index:02d}+00:00",
            "predicted_tag": "Weakness" if index == 1 else "Strength",
            "input_text": f"Text for {analysis_id}",
        }
        for index, analysis_id in enumerate(analysis_ids, start=1)
    ]
    replace_analysis_history(analysis_records)
    replace_grading_history(grading_records)


def grading(
    analysis_id,
    *,
    completeness,
    readiness,
    missing=None,
    status="Needs Revision",
    section_scores=None,
):
    return {
        "id": f"grading-{analysis_id}",
        "analysis_id": analysis_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "semantic_percentage": 70,
        "percentage_score": 70,
        "proposal_completeness": {
            "percentage": completeness,
            "missing_sections": missing or [],
        },
        "completeness_percentage": completeness,
        "final_readiness": {"percentage": readiness, "label": status},
        "final_readiness_percentage": readiness,
        "final_readiness_label": status,
        "missing_sections": missing or [],
        "submission_status": status,
        "submission_readiness": {"status": status},
        "section_scores": section_scores or {},
    }


def create_proposal_with_versions(database_path, version_count=2, proposal_title="Proposal"):
    connection = connect(database_path)
    try:
        student = create_student(connection, academic_student_id=f"IT{proposal_title}", full_name=f"{proposal_title} Student")
        proposal = create_proposal(connection, student_id=student["student_id"], title=proposal_title)
        versions = [
            create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=index,
                original_filename="proposal.pdf",
                source_type="pdf",
                extracted_text=f"Version {index}",
            )
            for index in range(1, version_count + 1)
        ]
        return proposal, versions
    finally:
        connection.close()


def link_analysis(database_path, proposal_id, version_id, analysis_id):
    connection = connect(database_path)
    try:
        return create_analysis(
            connection,
            proposal_id=proposal_id,
            version_id=version_id,
            analysis_id=analysis_id,
            request_id=analysis_id,
            source="pdf",
            input_text_snapshot=f"Snapshot {analysis_id}",
        )
    finally:
        connection.close()


def save_review(database_path, proposal_id, version_id, decision):
    connection = connect(database_path)
    try:
        supervisor = connection.execute(
            "SELECT * FROM supervisor_profiles WHERE supervisor_id = ?",
            ("supervisor-dev",),
        ).fetchone()
        if supervisor is None:
            user = create_user(
                connection,
                email="improvement-supervisor@example.test",
                role="supervisor",
                display_name="Improvement Supervisor",
            )
            create_supervisor_profile(
                connection,
                user_id=user["user_id"],
                department="Computing",
                title="Dr.",
                supervisor_id="supervisor-dev",
            )
        return create_supervisor_review(
            connection,
            proposal_id=proposal_id,
            version_id=version_id,
            supervisor_id="supervisor-dev",
            decision=decision,
        )
    finally:
        connection.close()


def test_one_version_proposal_returns_snapshot_without_comparison(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=1)
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    write_history(history_dir, ["A1"], [grading("A1", completeness=80, readiness=70, missing=["References"])])

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert len(payload["versions"]) == 1
    assert payload["versions"][0]["analysis_id"] == "A1"
    assert payload["comparisons"] == []


def test_improved_comparison_same_filename_and_section_deltas(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path)
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=60, readiness=50, missing=["Evaluation", "References"], section_scores={"Methodology": 61}),
            grading("A2", completeness=90, readiness=75, missing=["References"], status="Developing", section_scores={"Methodology": 76}),
        ],
    )

    comparison = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()["comparisons"][0]

    assert comparison["from_analysis_id"] == "A1"
    assert comparison["to_analysis_id"] == "A2"
    assert comparison["completeness_delta"] == 30
    assert comparison["readiness_delta"] == 25
    assert comparison["resolved_missing_sections"] == ["Evaluation"]
    assert comparison["still_missing_sections"] == ["References"]
    assert comparison["section_score_changes"] == [{"section": "Methodology", "from_score": 61.0, "to_score": 76.0, "delta": 15.0}]
    assert comparison["status_change"]["changed"] is True
    assert comparison["overall_direction"] == "IMPROVED"


def test_regressed_comparison_with_newly_missing_section(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path)
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=90, readiness=80, missing=[], status="Ready", section_scores={"Evaluation": 80}),
            grading("A2", completeness=70, readiness=60, missing=["Evaluation"], status="Needs Revision", section_scores={"Evaluation": 55}),
        ],
    )

    comparison = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()["comparisons"][0]

    assert comparison["completeness_delta"] == -20
    assert comparison["readiness_delta"] == -20
    assert comparison["newly_missing_sections"] == ["Evaluation"]
    assert comparison["overall_direction"] == "REGRESSED"


def test_mixed_and_unchanged_direction_rules(improvement_client):
    client, database_path, history_dir = improvement_client
    mixed_proposal, mixed_versions = create_proposal_with_versions(database_path, proposal_title="Mixed")
    unchanged_proposal, unchanged_versions = create_proposal_with_versions(database_path, proposal_title="Unchanged")
    for proposal, versions, ids in [
        (mixed_proposal, mixed_versions, ("M1", "M2")),
        (unchanged_proposal, unchanged_versions, ("U1", "U2")),
    ]:
        link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], ids[0])
        link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], ids[1])
    write_history(
        history_dir,
        ["M1", "M2", "U1", "U2"],
        [
            grading("M1", completeness=60, readiness=80, missing=["Evaluation"]),
            grading("M2", completeness=80, readiness=60, missing=[]),
            grading("U1", completeness=80, readiness=70, missing=["References"]),
            grading("U2", completeness=80, readiness=70, missing=["References"]),
        ],
    )

    mixed = client.get(f"/proposals/{mixed_proposal['proposal_id']}/improvement").json()["comparisons"][0]
    unchanged = client.get(f"/proposals/{unchanged_proposal['proposal_id']}/improvement").json()["comparisons"][0]

    assert mixed["overall_direction"] == "MIXED"
    assert unchanged["overall_direction"] == "UNCHANGED"


def test_missing_analysis_and_missing_grading_are_unavailable_not_zero(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path)
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    write_history(history_dir, ["A1"], [])

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["versions"][0]["analyzed"] is True
    assert payload["versions"][0]["grading_history_available"] is False
    assert payload["versions"][0]["completeness_percentage"] is None
    assert payload["versions"][1]["analyzed"] is False
    assert payload["versions"][1]["analysis_id"] is None
    assert payload["comparisons"][0]["overall_direction"] == "INSUFFICIENT_DATA"


def test_v1_analyzed_v2_waiting_keeps_comparison_unavailable(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path)
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    write_history(history_dir, ["A1"], [grading("A1", completeness=85, readiness=75, missing=["References"])])

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["versions"][0]["version_id"] == versions[0]["version_id"]
    assert payload["versions"][0]["analyzed"] is True
    assert payload["versions"][0]["analysis_id"] == "A1"
    assert payload["versions"][0]["grading_history_available"] is True
    assert payload["versions"][0]["completeness_percentage"] == 85.0
    assert payload["versions"][1]["version_id"] == versions[1]["version_id"]
    assert payload["versions"][1]["analyzed"] is False
    assert payload["versions"][1]["analysis_id"] is None
    assert payload["versions"][1]["grading_history_available"] is False
    assert payload["comparisons"][0]["from_analysis_id"] == "A1"
    assert payload["comparisons"][0]["to_analysis_id"] is None
    assert payload["comparisons"][0]["completeness_delta"] is None
    assert payload["comparisons"][0]["readiness_delta"] is None
    assert payload["comparisons"][0]["overall_direction"] == "INSUFFICIENT_DATA"


def test_latest_analysis_per_version_is_selected_deterministically(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path)
    for analysis_id, version in [("A1", versions[0]), ("A3", versions[0]), ("A2", versions[1]), ("A4", versions[1])]:
        link_analysis(database_path, proposal["proposal_id"], version["version_id"], analysis_id)
    write_history(
        history_dir,
        ["A1", "A2", "A3", "A4"],
        [
            grading("A1", completeness=50, readiness=40),
            grading("A2", completeness=60, readiness=50),
            grading("A3", completeness=70, readiness=60),
            grading("A4", completeness=90, readiness=80),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert [version["analysis_id"] for version in payload["versions"]] == ["A3", "A4"]
    assert payload["comparisons"][0]["from_analysis_id"] == "A3"
    assert payload["comparisons"][0]["to_analysis_id"] == "A4"


def test_three_versions_return_sequential_adjacent_comparisons(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=3, proposal_title="Sequential")
    for analysis_id, version in zip(["A1", "A2", "A3"], versions):
        link_analysis(database_path, proposal["proposal_id"], version["version_id"], analysis_id)
    write_history(
        history_dir,
        ["A1", "A2", "A3"],
        [
            grading("A1", completeness=50, readiness=40, missing=["Abstract", "Objectives"]),
            grading("A2", completeness=75, readiness=65, missing=["Objectives"]),
            grading("A3", completeness=100, readiness=90, missing=[]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert [version["version_number"] for version in payload["versions"]] == [1, 2, 3]
    assert [(item["from_version"], item["to_version"]) for item in payload["comparisons"]] == [(1, 2), (2, 3)]
    assert payload["comparisons"][0]["resolved_missing_sections"] == ["Abstract"]
    assert payload["comparisons"][0]["still_missing_sections"] == ["Objectives"]
    assert payload["comparisons"][1]["resolved_missing_sections"] == ["Objectives"]
    assert payload["comparisons"][1]["still_missing_sections"] == []


def test_cross_proposal_isolation(improvement_client):
    client, database_path, history_dir = improvement_client
    p1, p1_versions = create_proposal_with_versions(database_path, proposal_title="P1")
    p2, p2_versions = create_proposal_with_versions(database_path, version_count=1, proposal_title="P2")
    link_analysis(database_path, p1["proposal_id"], p1_versions[0]["version_id"], "A1")
    link_analysis(database_path, p1["proposal_id"], p1_versions[1]["version_id"], "A2")
    link_analysis(database_path, p2["proposal_id"], p2_versions[0]["version_id"], "A3")
    write_history(
        history_dir,
        ["A1", "A2", "A3"],
        [
            grading("A1", completeness=60, readiness=50),
            grading("A2", completeness=80, readiness=70),
            grading("A3", completeness=100, readiness=95),
        ],
    )

    payload = client.get(f"/proposals/{p1['proposal_id']}/improvement").json()

    assert [version["analysis_id"] for version in payload["versions"]] == ["A1", "A2"]
    assert "A3" not in json.dumps(payload)


def test_best_available_version_selects_v2_for_structural_regression_example(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=3, proposal_title="BestExample")
    for analysis_id, version in zip(["A1", "A2", "A3"], versions):
        link_analysis(database_path, proposal["proposal_id"], version["version_id"], analysis_id)
        save_review(database_path, proposal["proposal_id"], version["version_id"], "REVISION_REQUESTED")
    write_history(
        history_dir,
        ["A1", "A2", "A3"],
        [
            grading("A1", completeness=40, readiness=40, missing=["Abstract", "Introduction", "Literature Review"]),
            grading("A2", completeness=100, readiness=70, missing=[]),
            grading("A3", completeness=80, readiness=65, missing=["Abstract"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[1]["version_id"]
    assert payload["best_version"]["version_number"] == 2
    assert payload["best_version"]["version_label"] == "V2"
    assert payload["latest_version"]["version_id"] == versions[2]["version_id"]
    assert payload["latest_is_best"] is False
    assert payload["regressions_after_best"] == [
        {"section": "Abstract", "message": "Abstract became missing in V3"}
    ]
    assert "No missing sections" in payload["best_version"]["reasons"]
    assert any("Resolved Abstract, Introduction and Literature Review" == reason for reason in payload["best_version"]["reasons"])


def test_latest_version_is_not_automatically_selected(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=3, proposal_title="NotLatest")
    for analysis_id, version in zip(["A1", "A2", "A3"], versions):
        link_analysis(database_path, proposal["proposal_id"], version["version_id"], analysis_id)
    write_history(
        history_dir,
        ["A1", "A2", "A3"],
        [
            grading("A1", completeness=75, readiness=60, missing=["Abstract"]),
            grading("A2", completeness=100, readiness=70, missing=[]),
            grading("A3", completeness=65, readiness=65, missing=["Abstract", "Evaluation"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[1]["version_id"]
    assert payload["latest_is_best"] is False


def test_approved_version_outranks_revision_requested_when_evidence_is_comparable(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="DecisionRank")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    save_review(database_path, proposal["proposal_id"], versions[0]["version_id"], "READY_FOR_PANEL")
    save_review(database_path, proposal["proposal_id"], versions[1]["version_id"], "REVISION_REQUESTED")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=90, readiness=80, missing=["References"]),
            grading("A2", completeness=90, readiness=80, missing=["References"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[0]["version_id"]
    assert payload["best_version"]["supervisor_decision"] == "READY_FOR_PANEL"


def test_best_available_prefers_fewer_missing_sections(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="FewerMissing")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=60, readiness=80, missing=["Abstract", "Evaluation"]),
            grading("A2", completeness=80, readiness=70, missing=["Evaluation"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[1]["version_id"]


def test_newly_missing_sections_count_as_regressions(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="RegressionRank")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=100, readiness=80, missing=[]),
            grading("A2", completeness=80, readiness=85, missing=["Abstract"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[0]["version_id"]
    assert payload["regressions_after_best"] == [
        {"section": "Abstract", "message": "Abstract became missing in V2"}
    ]


def test_unanalyzed_versions_are_excluded_from_best_selection(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="Unanalyzed")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    write_history(history_dir, ["A1"], [grading("A1", completeness=75, readiness=60, missing=["References"])])

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[0]["version_id"]
    assert payload["best_version"]["eligible_version_count"] == 1


def test_select_best_available_rejects_mixed_proposals():
    with pytest.raises(ValueError):
        select_best_available_version(
            [
                {"proposal_id": "P1", "version_id": "V1", "version_number": 1, "analyzed": True, "analysis_history_available": True},
                {"proposal_id": "P2", "version_id": "V2", "version_number": 2, "analyzed": True, "analysis_history_available": True},
            ],
            [],
        )


def test_one_eligible_version_selects_itself(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=1, proposal_title="SingleBest")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    write_history(history_dir, ["A1"], [grading("A1", completeness=80, readiness=75, missing=["References"])])

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[0]["version_id"]
    assert payload["latest_is_best"] is True


def test_no_eligible_version_returns_no_best_version(improvement_client):
    client, database_path, _ = improvement_client
    proposal, _ = create_proposal_with_versions(database_path, version_count=2, proposal_title="NoBest")

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"] is None
    assert payload["latest_is_best"] is False


def test_best_available_ties_resolve_to_latest_deterministically(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="TieBest")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=90, readiness=80, missing=["References"]),
            grading("A2", completeness=90, readiness=80, missing=["References"]),
        ],
    )

    payload = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()

    assert payload["best_version"]["version_id"] == versions[1]["version_id"]
    assert payload["latest_is_best"] is True


def test_missing_metrics_are_not_treated_as_zero():
    best = select_best_available_version(
        [
            {
                "proposal_id": "P1",
                "version_id": "V1",
                "version_number": 1,
                "analyzed": True,
                "analysis_history_available": True,
                "grading_history_available": False,
                "supervisor_decision": None,
            },
            {
                "proposal_id": "P1",
                "version_id": "V2",
                "version_number": 2,
                "analyzed": True,
                "analysis_history_available": True,
                "grading_history_available": True,
                "missing_sections": ["Abstract"],
                "supervisor_decision": None,
            },
        ],
        [],
    )

    assert best["version_id"] == "V2"
    assert best["used_partial_evidence"] is True
    assert "missing_sections" not in best["metrics_used"]


def test_selection_reasons_match_actual_evidence(improvement_client):
    client, database_path, history_dir = improvement_client
    proposal, versions = create_proposal_with_versions(database_path, version_count=2, proposal_title="Reasons")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    save_review(database_path, proposal["proposal_id"], versions[1]["version_id"], "REVISION_REQUESTED")
    write_history(
        history_dir,
        ["A1", "A2"],
        [
            grading("A1", completeness=50, readiness=55, missing=["Abstract"]),
            grading("A2", completeness=100, readiness=65, missing=[]),
        ],
    )

    reasons = client.get(f"/proposals/{proposal['proposal_id']}/improvement").json()["best_version"]["reasons"]

    assert "No missing sections" in reasons
    assert "Resolved Abstract" in reasons
    assert "No structural regressions" in reasons
    assert "Supervisor revision is still requested" in reasons


def test_unknown_proposal_improvement_returns_404(improvement_client):
    client, _, _ = improvement_client

    response = client.get("/proposals/missing/improvement")

    assert response.status_code == 404
