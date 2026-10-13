import json
import sys
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.database import get_db_connection
from src.api.routers import supervisor
from src.api.schemas import SupervisorReviewDraftContent
from src.api.services import core_logic
from src.api.services import resend_service as email_service
from src.core import knowledge_graph
from src.db import repositories
from tests.postgres_fixtures import connect
from src.db.repositories import (
    assign_supervisor_to_student,
    create_analysis,
    create_proposal,
    create_proposal_version,
    create_student,
    create_supervisor_profile,
    create_user,
)
from src.db.history_repositories import (
    list_grading_history,
    replace_analysis_history,
    replace_grading_history,
    replace_graph_history,
)
from tests.postgres_fixtures import create_schema


@pytest.fixture()
def draft_client(tmp_path, monkeypatch):
    database_path = tmp_path / "review_drafts.postgresql"
    history_dir = tmp_path / "history"
    history_dir.mkdir()
    monkeypatch.setattr(core_logic, "DATA_DIR", history_dir)
    monkeypatch.setattr(knowledge_graph, "DATA_DIR", history_dir)

    call_count = {"count": 0}

    def fake_generate(evidence):
        call_count["count"] += 1
        assert evidence["analysis_id"]
        assert evidence["proposal_text"]
        return (
            SupervisorReviewDraftContent(
                overall_assessment="The proposal is analyzable and has a clear academic direction.",
                strengths=["The topic is relevant to supervisor-centered proposal review."],
                areas_requiring_improvement=["Clarify the research gap using the retrieved feedback evidence."],
                methodology_feedback="Expand the method design, sampling plan, and data collection procedure.",
                evaluation_validation_feedback="Define validation metrics and explain how evaluation evidence will be collected.",
                recommendations=["Use the recommended research methods resource to strengthen the design."],
                suggested_revision_instructions=["Revise the methodology and evaluation sections before resubmission."],
            ),
            {"provider": "fake", "prompt_version": "test"},
        )

    monkeypatch.setattr(supervisor, "generate_structured_supervisor_review_draft", fake_generate)
    monkeypatch.setattr(
        supervisor,
        "validate_structured_supervisor_review_draft",
        lambda raw_draft, evidence: (raw_draft, {"provider": "fake-validator"}),
    )

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
    return TestClient(app), database_path, analysis_history_path, grading_history_path, call_count


def create_proposal_fixture(database_path, *, version_count=1, student_email=None):
    connection = connect(database_path)
    try:
        student = create_student(
            connection,
            academic_student_id="ITDRAFT",
            full_name="Draft Student",
            email=student_email,
        )
        proposal = create_proposal(connection, student_id=student["student_id"], title="Draft Proposal")
        versions = [
            create_proposal_version(
                connection,
                proposal_id=proposal["proposal_id"],
                version_number=index,
                original_filename=f"draft-v{index}.pdf",
                source_type="pdf",
                extracted_text=(
                    "Abstract This research investigates supervisor review workflows. "
                    "Introduction The study explains the academic context. "
                    "Research Gap Existing systems lack structured review drafts. "
                    "Objectives The objectives are to analyze and improve proposal review. "
                    "Methodology The method uses prototype evaluation and document analysis. "
                    "Literature Review Previous studies discuss academic feedback systems. "
                    "Evaluation The evaluation uses accuracy, completeness, and usability metrics. "
                    "References Smith 2024."
                ),
            )
            for index in range(1, version_count + 1)
        ]
        return proposal, versions
    finally:
        connection.close()


def analysis_history_record(analysis_id):
    return {
        "id": analysis_id,
        "analysis_id": analysis_id,
        "request_id": analysis_id,
        "source": "pdf",
        "filename": "draft.pdf",
        "input_text": "Completed proposal text with methodology and evaluation evidence.",
        "predicted_tag": "Methodology Weakness",
        "classification_reason": "Methodology needs more detail.",
        "retrieved_feedback": [{"comment_text": "Clarify the data collection method."}],
        "recommended_resources": [{"title": "Research Methods Guide", "type": "Guide"}],
    }


def grading_history_record(analysis_id):
    return {
        "id": f"grading-{analysis_id}",
        "analysis_id": analysis_id,
        "predicted_score": 31.0,
        "max_score": 42,
        "percentage_score": 73.81,
        "score_label": "Good",
        "section_scores": {"Methodology": 3},
        "proposal_completeness": {"percentage": 80, "missing_sections": ["Evaluation"]},
        "submission_readiness": {"status": "Needs Revision"},
        "final_readiness": {"percentage": 76, "label": "Needs Revision"},
        "missing_sections": ["Evaluation"],
    }


def write_histories(analysis_path, grading_path, analysis_ids):
    replace_analysis_history([analysis_history_record(analysis_id) for analysis_id in analysis_ids])
    replace_grading_history([grading_history_record(analysis_id) for analysis_id in analysis_ids])


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
            input_text_snapshot=f"Snapshot for {analysis_id}",
        )
    finally:
        connection.close()


def create_assigned_supervisor(database_path, student_id, email="draft-supervisor@example.test"):
    connection = connect(database_path)
    try:
        user = create_user(connection, email=email, role="supervisor", display_name="Draft Supervisor")
        supervisor_profile = create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
        assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            student_id=student_id,
            assignment_role="primary_supervisor",
        )
        return supervisor_profile
    finally:
        connection.close()


def edited_payload(supervisor_id, analysis_id="A1", *, suffix="", comments="Human supervisor comment."):
    return {
        "analysis_id": analysis_id,
        "supervisor_id": supervisor_id,
        "overall_assessment": f"Edited overall assessment{suffix}.",
        "strengths": [f"Edited strength{suffix}."],
        "areas_requiring_improvement": [f"Edited improvement{suffix}."],
        "methodology_feedback": f"Edited methodology feedback{suffix}.",
        "evaluation_validation_feedback": f"Edited evaluation feedback{suffix}.",
        "recommendations": [f"Edited recommendation{suffix}."],
        "suggested_revision_instructions": [f"Edited revision instruction{suffix}."],
        "supervisor_comments": comments,
    }


def final_pdf(client, version_id, analysis_id, supervisor_id):
    return client.get(
        f"/versions/{version_id}/final-feedback.pdf",
        params={"analysis_id": analysis_id, "supervisor_id": supervisor_id},
    )


def pdf_text(response):
    return pdf_extracted_text(response)


def pdf_extracted_text(response):
    reader = PdfReader(BytesIO(response.content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def pdf_uri_annotations(response):
    reader = PdfReader(BytesIO(response.content))
    uris = []
    for page in reader.pages:
        annotations = page.get("/Annots") or []
        for annotation_ref in annotations:
            annotation = annotation_ref.get_object()
            action = annotation.get("/A") or {}
            uri = action.get("/URI")
            if uri:
                uris.append(str(uri))
    return uris


def text_between(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start)
    return text[start:] if end == -1 else text[start:end]


def delivery_state(client, version_id, analysis_id, supervisor_id):
    return client.get(
        f"/versions/{version_id}/feedback-delivery",
        params={"analysis_id": analysis_id, "supervisor_id": supervisor_id},
    )


def send_feedback(client, version_id, analysis_id, supervisor_id):
    return client.post(
        f"/versions/{version_id}/send-feedback",
        json={"analysis_id": analysis_id, "supervisor_id": supervisor_id},
    )


def review_outcome(client, version_id, analysis_id, supervisor_id, decision, comments=None):
    return client.post(
        f"/versions/{version_id}/review-outcome",
        json={
            "analysis_id": analysis_id,
            "supervisor_id": supervisor_id,
            "decision": decision,
            "comments": comments,
        },
    )


def get_review_outcome(client, version_id, analysis_id, supervisor_id):
    return client.get(
        f"/versions/{version_id}/review-outcome",
        params={"analysis_id": analysis_id, "supervisor_id": supervisor_id},
    )


def create_revised_version(client, proposal_id, supervisor_id, filename="draft-v2.pdf", extracted_text="Revised proposal text."):
    return client.post(
        f"/proposals/{proposal_id}/revised-versions",
        json={
            "supervisor_id": supervisor_id,
            "original_filename": filename,
            "source_type": "pdf",
            "extracted_text": extracted_text,
        },
    )


def generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, version, analysis_id="A1"):
    write_histories(analysis_path, grading_path, [analysis_id])
    link_analysis(database_path, proposal["proposal_id"], version["version_id"], analysis_id)
    response = client.post(f"/versions/{version['version_id']}/review-draft", json={"analysis_id": analysis_id})
    assert response.status_code == 201
    return response.json()


def write_custom_histories(analysis_path, grading_path, analysis_records, grading_records):
    replace_analysis_history(analysis_records)
    replace_grading_history(grading_records)


def test_analyzed_v1_can_generate_persistent_review_draft_without_v2(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=1)
    write_histories(analysis_path, grading_path, ["A1"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})

    assert response.status_code == 201
    payload = response.json()
    assert payload["proposal_id"] == proposal["proposal_id"]
    assert payload["version_id"] == versions[0]["version_id"]
    assert payload["analysis_id"] == "A1"
    assert payload["draft"]["overall_assessment"]
    assert payload["draft"]["strengths"]
    assert payload["draft"]["areas_requiring_improvement"]
    assert payload["draft"]["methodology_feedback"]
    assert payload["draft"]["evaluation_validation_feedback"]
    assert payload["draft"]["recommendations"]
    assert payload["draft"]["suggested_revision_instructions"]
    assert payload["evidence_summary"]["proposal_text_used"] is True
    assert call_count["count"] == 1

    saved = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A1"})
    assert saved.status_code == 200
    assert saved.json()["draft_id"] == payload["draft_id"]
    assert call_count["count"] == 1


def test_main_app_registers_review_draft_route_and_generates_for_linked_v1(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    write_histories(analysis_path, grading_path, ["A1"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")

    from src.api.main import app as main_app

    previous_database_url = getattr(main_app.state, "database_url", None)
    main_app.state.database_url = "postgresql-test"
    try:
        main_client = TestClient(main_app)
        response = main_client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    finally:
        main_app.state.database_url = previous_database_url

    assert response.status_code == 201
    assert response.json()["analysis_id"] == "A1"


def test_unlinked_analysis_id_is_rejected(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    _, versions = create_proposal_fixture(database_path)
    write_histories(analysis_path, grading_path, ["A1"])

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})

    assert response.status_code == 409
    assert call_count["count"] == 0


def test_valid_linked_analysis_without_ai_draft_is_reported_as_not_found_state(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    write_histories(analysis_path, grading_path, ["A1"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")

    missing = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A1"})
    assert missing.status_code == 404
    assert missing.json()["detail"] == "AI supervisor review draft not found."
    assert call_count["count"] == 0

    generated = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    loaded = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A1"})

    assert generated.status_code == 201
    assert generated.json()["analysis_id"] == "A1"
    assert loaded.status_code == 200
    assert loaded.json()["draft_id"] == generated.json()["draft_id"]
    assert call_count["count"] == 1


def test_analysis_linked_to_another_version_is_rejected(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    write_histories(analysis_path, grading_path, ["A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A2"})

    assert response.status_code == 409
    assert call_count["count"] == 0


def test_newer_analysis_without_draft_does_not_reuse_older_analysis_drafts(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "multi-analysis@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A2")
    a1 = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    assert a1.status_code == 201
    saved_a1 = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1", suffix=" A1"),
    )
    assert saved_a1.status_code == 200

    missing_a2 = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A2"})
    human_a2_before_ai = client.get(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        params={"analysis_id": "A2", "supervisor_id": supervisor_profile["supervisor_id"]},
    )
    final_a2_before_ai = final_pdf(client, versions[0]["version_id"], "A2", supervisor_profile["supervisor_id"])
    a2 = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A2"})
    human_a2_after_ai = client.get(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        params={"analysis_id": "A2", "supervisor_id": supervisor_profile["supervisor_id"]},
    )
    final_a2_without_human = final_pdf(client, versions[0]["version_id"], "A2", supervisor_profile["supervisor_id"])
    a1_after = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A1"})

    assert missing_a2.status_code == 404
    assert missing_a2.json()["detail"] == "AI supervisor review draft not found."
    assert human_a2_before_ai.status_code == 404
    assert human_a2_before_ai.json()["detail"] == "AI supervisor review draft not found."
    assert final_a2_before_ai.status_code == 404
    assert final_a2_before_ai.json()["detail"] == "AI supervisor review draft not found."
    assert a2.status_code == 201
    assert a2.json()["analysis_id"] == "A2"
    assert a2.json()["draft_id"] != a1.json()["draft_id"]
    assert human_a2_after_ai.status_code == 404
    assert human_a2_after_ai.json()["detail"] == "Supervisor review draft not found."
    assert final_a2_without_human.status_code == 409
    assert final_a2_without_human.json()["detail"] == "Save the supervisor review before generating the final feedback PDF."
    assert a1_after.status_code == 200
    assert a1_after.json()["draft_id"] == a1.json()["draft_id"]
    assert call_count["count"] == 2


def test_existing_draft_is_returned_without_regeneration(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    write_histories(analysis_path, grading_path, ["A1"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")

    first = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    second = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["draft_id"] == second.json()["draft_id"]
    assert call_count["count"] == 1


def test_second_analyzed_version_uses_same_review_draft_architecture(draft_client):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")

    v1 = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    v2 = client.post(f"/versions/{versions[1]['version_id']}/review-draft", json={"analysis_id": "A2"})

    assert v1.status_code == 201
    assert v2.status_code == 201
    assert v1.json()["version_id"] == versions[0]["version_id"]
    assert v2.json()["version_id"] == versions[1]["version_id"]
    assert v1.json()["draft_id"] != v2.json()["draft_id"]
    assert call_count["count"] == 2


def test_review_draft_uses_model_evidence_for_actionable_revision_guidance(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    captured = {}
    analysis_record = {
        "id": "A_METHOD",
        "analysis_id": "A_METHOD",
        "request_id": "A_METHOD",
        "source": "pdf",
        "filename": "methodology-gap.pdf",
        "input_text": (
            "Abstract This proposal studies automated proposal review. "
            "Introduction The work targets supervisor feedback workflows. "
            "Objectives The objective is to improve revision guidance. "
            "Literature Review Prior systems provide limited feedback. "
            "Evaluation The evaluation is not fully defined."
        ),
        "predicted_tag": "Methodology Weakness",
        "model_predicted_tag": "Methodology Weakness",
        "classification_reason": "The method design is incomplete and baseline comparison is missing.",
        "retrieved_feedback": [
            {"comment_text": "Clarify sampling, data collection steps, and baseline model comparison."},
            {"comment_text": "Define evaluation metrics before claiming system effectiveness."},
        ],
        "recommended_resources": [
            {"title": "Designing a Reproducible Methodology", "type": "Guide"},
            {"title": "Evaluation Metrics for Applied ML Systems", "type": "Guide"},
        ],
    }
    grading_record = {
        "id": "grading-A_METHOD",
        "analysis_id": "A_METHOD",
        "predicted_score": 19.0,
        "max_score": 42,
        "percentage_score": 45.24,
        "score_label": "Needs Improvement",
        "section_scores": {"Methodology": 1, "Evaluation": 1},
        "proposal_completeness": {"percentage": 60, "missing_sections": ["Methodology"]},
        "submission_readiness": {"status": "Needs Revision"},
        "final_readiness": {"percentage": 52, "label": "Needs Major Revision"},
        "missing_sections": ["Methodology"],
    }
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_record])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A_METHOD")

    def evidence_aware_generate(evidence):
        captured["evidence"] = evidence
        assert evidence["analysis_id"] == "A_METHOD"
        assert evidence["version_number"] == 1
        assert "Structural proposal weakness detected" in evidence["classification_reason"]
        assert evidence["semantic_grade"]["proposal_completeness"]["missing_sections"] == ["Methodology"]
        assert evidence["semantic_grade"]["final_readiness"]["label"] == "Major Revision Required"
        assert any("baseline model comparison" in item["comment_text"] for item in evidence["retrieved_feedback"])
        assert any(resource["title"] == "Designing a Reproducible Methodology" for resource in evidence["recommended_resources"])
        return (
            SupervisorReviewDraftContent(
                overall_assessment="The proposal needs major revision because Analyzer evidence shows incomplete methodology and evaluation planning.",
                strengths=["The proposal has a clear supervisor feedback workflow target."],
                areas_requiring_improvement=[
                    "Methodology is incomplete: clarify sampling, data collection steps, and baseline model comparison.",
                    "Evaluation is weak: define metrics before claiming system effectiveness.",
                ],
                methodology_feedback="Add the research design, sampling plan, data collection procedure, and baseline model comparison supported by the Analyzer feedback.",
                evaluation_validation_feedback="Define evaluation metrics and validation evidence before reporting effectiveness.",
                recommendations=[
                    "Use Designing a Reproducible Methodology to strengthen method structure.",
                    "Use Evaluation Metrics for Applied ML Systems to select measurable validation criteria.",
                ],
                suggested_revision_instructions=[
                    "Revise the Methodology section with sampling, procedure, data collection, and baseline comparison details.",
                    "Revise the Evaluation section with metrics, validation criteria, and evidence collection steps.",
                ],
            ),
            {"provider": "fake", "prompt_version": "evidence-chain-test"},
        )

    monkeypatch.setattr(supervisor, "generate_structured_supervisor_review_draft", evidence_aware_generate)

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A_METHOD"})

    assert response.status_code == 201
    payload = response.json()
    assert "Methodology is incomplete" in payload["draft"]["areas_requiring_improvement"][0]
    assert "baseline model comparison" in payload["draft"]["methodology_feedback"]
    assert "evaluation metrics" in payload["draft"]["evaluation_validation_feedback"]
    assert "Revise the Methodology section" in payload["draft"]["suggested_revision_instructions"][0]
    assert captured["evidence"]["semantic_grade"]["section_scores"] == {"Methodology": 1, "Evaluation": 1}
    assert payload["evidence_summary"]["semantic_rubric_used"] is True
    assert payload["evidence_summary"]["completeness_used"] is True
    assert payload["evidence_summary"]["final_readiness_used"] is True
    assert payload["evidence_summary"]["recommendations_used"] is True
    assert payload["evidence_summary"]["retrieved_feedback"] == analysis_record["retrieved_feedback"]
    assert payload["evidence_summary"]["recommended_resources"] == analysis_record["recommended_resources"]
    assert payload["evidence_summary"]["retrieved_feedback_count"] == 2
    assert payload["evidence_summary"]["missing_sections"] == ["Methodology"]
    assert "Designing a Reproducible Methodology" in payload["evidence_summary"]["recommended_resource_titles"]

    loaded = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A_METHOD"})
    assert loaded.status_code == 200
    assert loaded.json()["evidence_summary"]["retrieved_feedback"] == analysis_record["retrieved_feedback"]
    assert loaded.json()["evidence_summary"]["recommended_resources"] == analysis_record["recommended_resources"]


def test_evidence_grounded_revision_guidance_survives_supervisor_edit_and_final_pdf(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "evidence-final@example.test")
    analysis_record = {
        "id": "A_REVISION",
        "analysis_id": "A_REVISION",
        "request_id": "A_REVISION",
        "source": "pdf",
        "filename": "revision-guidance.pdf",
        "input_text": "Abstract Proposed system. Introduction Context. Objectives Improve feedback. Evaluation Weak evaluation.",
        "predicted_tag": "Weakness",
        "classification_reason": "Methodology incomplete and evaluation metrics are under-specified.",
        "retrieved_feedback": [{"comment_text": "Add baseline comparison and justify selected evaluation metrics."}],
        "recommended_resources": [{"title": "Evaluation Metrics for Applied ML Systems", "type": "Guide"}],
    }
    grading_record = {
        "id": "grading-A_REVISION",
        "analysis_id": "A_REVISION",
        "predicted_score": 18.0,
        "max_score": 42,
        "percentage_score": 42.86,
        "score_label": "Needs Improvement",
        "section_scores": {"Methodology": 1, "Evaluation": 1},
        "proposal_completeness": {"percentage": 60, "missing_sections": ["Methodology", "Evaluation"]},
        "submission_readiness": {"status": "Needs Revision"},
        "final_readiness": {"percentage": 50, "label": "Needs Major Revision"},
        "missing_sections": ["Methodology", "Evaluation"],
    }
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_record])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A_REVISION")

    def evidence_aware_generate(evidence):
        return (
            SupervisorReviewDraftContent(
                overall_assessment="Analyzer evidence indicates major revision is needed before resubmission.",
                strengths=["The topic is relevant."],
                areas_requiring_improvement=["Methodology and evaluation are incomplete according to Analyzer evidence."],
                methodology_feedback="Clarify method steps and add baseline comparison.",
                evaluation_validation_feedback="Justify selected evaluation metrics and validation criteria.",
                recommendations=["Use Evaluation Metrics for Applied ML Systems."],
                suggested_revision_instructions=["Add baseline comparison and justify selected evaluation metrics before preparing V2."],
            ),
            {"provider": "fake", "prompt_version": "final-pdf-evidence-chain-test"},
        )

    monkeypatch.setattr(supervisor, "generate_structured_supervisor_review_draft", evidence_aware_generate)
    generated = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A_REVISION"})
    assert generated.status_code == 201
    approved_instruction = "Supervisor-approved instruction: add baseline comparison and justify selected evaluation metrics before preparing V2."
    approved_comment = "Supervisor comment: focus the revision on measurable validation evidence."
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json={
            "analysis_id": "A_REVISION",
            "supervisor_id": supervisor_profile["supervisor_id"],
            "overall_assessment": "Supervisor-approved overall assessment for revision.",
            "strengths": ["Supervisor-approved strength."],
            "areas_requiring_improvement": ["Supervisor-approved methodology and evaluation gap."],
            "methodology_feedback": "Supervisor-approved methodology feedback with baseline comparison.",
            "evaluation_validation_feedback": "Supervisor-approved evaluation feedback with selected metrics.",
            "recommendations": ["Supervisor-approved evaluation metrics resource."],
            "suggested_revision_instructions": [approved_instruction],
            "supervisor_comments": approved_comment,
        },
    )
    response = final_pdf(client, versions[0]["version_id"], "A_REVISION", supervisor_profile["supervisor_id"])

    assert saved.status_code == 200
    assert response.status_code == 200
    pdf_text = response.content.decode("latin-1", errors="ignore")
    assert "Supervisor-approved instruction" in pdf_text
    assert "baseline comparison" in pdf_text
    assert "selected evaluation metrics" in pdf_text
    assert "Supervisor comment" in pdf_text
    assert "measurable validation evidence" in pdf_text
    assert "Add baseline comparison and justify selected evaluation metrics before preparing V2." not in pdf_text
    assert "SUPERVISOR COMMENTS" in pdf_text


def test_review_draft_rejects_wrong_analysis_before_using_unrelated_evidence(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, call_count = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    write_custom_histories(
        analysis_path,
        grading_path,
        [
            {**analysis_history_record("A1"), "classification_reason": "V1 methodology evidence."},
            {**analysis_history_record("A2"), "classification_reason": "UNRELATED V2 evidence must not be used."},
        ],
        [grading_history_record("A1"), grading_history_record("A2")],
    )
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    monkeypatch.setattr(
        supervisor,
        "generate_structured_supervisor_review_draft",
        lambda evidence: pytest.fail("Wrong-version evidence must not reach the draft generator."),
    )

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A2"})

    assert response.status_code == 409
    assert response.json()["detail"] == "This analysis_id is not linked to the requested proposal version."
    assert call_count["count"] == 0


def test_review_draft_generation_does_not_modify_model_scores(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    write_histories(analysis_path, grading_path, ["A1"])
    before = list_grading_history()[0]
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")

    response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})

    assert response.status_code == 201
    after = list_grading_history()[0]
    assert after["predicted_score"] == before["predicted_score"]
    assert after["percentage_score"] == before["percentage_score"]
    assert after["score_label"] == before["score_label"]
    assert after["proposal_completeness"] == before["proposal_completeness"]


def test_ai_draft_can_be_saved_as_supervisor_edited_review_without_overwriting_original(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"])
    ai_original = generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])

    response = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["version_id"] == versions[0]["version_id"]
    assert edited["analysis_id"] == "A1"
    assert edited["supervisor_id"] == supervisor_profile["supervisor_id"]
    assert edited["ai_draft_id"] == ai_original["draft_id"]
    assert edited["draft"]["overall_assessment"] == "Edited overall assessment."
    assert edited["supervisor_comments"] == "Human supervisor comment."

    ai_after = client.get(f"/versions/{versions[0]['version_id']}/review-draft", params={"analysis_id": "A1"}).json()
    assert ai_after["draft_id"] == ai_original["draft_id"]
    assert ai_after["draft"]["overall_assessment"] == ai_original["draft"]["overall_assessment"]


def test_get_returns_saved_human_edits_and_second_save_updates_same_review(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "save-again@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])

    first = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], comments="First comment."),
    ).json()
    second = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], suffix=" updated", comments="Updated comment."),
    ).json()

    assert second["review_id"] == first["review_id"]
    assert second["updated_at"] >= first["updated_at"]
    assert second["draft"]["methodology_feedback"] == "Edited methodology feedback updated."
    assert second["supervisor_comments"] == "Updated comment."

    loaded = client.get(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        params={"analysis_id": "A1", "supervisor_id": supervisor_profile["supervisor_id"]},
    )
    assert loaded.status_code == 200
    assert loaded.json()["review_id"] == first["review_id"]
    assert loaded.json()["draft"]["recommendations"] == ["Edited recommendation updated."]


def test_supervisor_review_draft_rejects_wrong_link_or_missing_ai_draft(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "wrong-link@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")

    wrong_version = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A2"),
    )
    assert wrong_version.status_code == 409

    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    missing_ai = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1"),
    )
    assert missing_ai.status_code == 404


def test_reviews_are_isolated_by_version_and_analysis(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "isolated@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2", "A3"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A3")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    for version, analysis_id in [(versions[0], "A1"), (versions[0], "A3"), (versions[1], "A2")]:
        response = client.post(f"/versions/{version['version_id']}/review-draft", json={"analysis_id": analysis_id})
        assert response.status_code == 201

    v1_a1 = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1", suffix=" V1A1"),
    ).json()
    v1_a3 = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A3", suffix=" V1A3"),
    ).json()
    v2_a2 = client.put(
        f"/versions/{versions[1]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A2", suffix=" V2A2"),
    ).json()

    assert len({v1_a1["review_id"], v1_a3["review_id"], v2_a2["review_id"]}) == 3
    assert v1_a1["draft"]["overall_assessment"] == "Edited overall assessment V1A1."
    assert v1_a3["draft"]["overall_assessment"] == "Edited overall assessment V1A3."
    assert v2_a2["draft"]["overall_assessment"] == "Edited overall assessment V2A2."


def test_review_editing_does_not_modify_model_score_records(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "scores@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    before = list_grading_history()[0]

    response = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )

    assert response.status_code == 200
    after = list_grading_history()[0]
    assert after["predicted_score"] == before["predicted_score"]
    assert after["percentage_score"] == before["percentage_score"]
    assert after["score_label"] == before["score_label"]
    assert after["proposal_completeness"] == before["proposal_completeness"]


def test_final_feedback_pdf_uses_saved_supervisor_edits_not_ai_original(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "final-report@example.test")
    ai_original = generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    original_draft = {**ai_original["draft"], "methodology_feedback": "AI ORIGINAL METHODOLOGY FEEDBACK"}
    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE ai_supervisor_review_drafts SET draft_json = ? WHERE draft_id = ?",
            (json.dumps(original_draft, ensure_ascii=False), ai_original["draft_id"]),
        )
        connection.commit()
    finally:
        connection.close()

    payload = edited_payload(supervisor_profile["supervisor_id"])
    payload["methodology_feedback"] = "SUPERVISOR EDITED METHODOLOGY FEEDBACK"
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    text = pdf_text(response)
    assert "SUPERVISOR EDITED METHODOLOGY FEEDBACK" in text
    assert "AI ORIGINAL METHODOLOGY FEEDBACK" not in text


def test_final_feedback_pdf_includes_saved_supervisor_comments_not_ai_text(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "comments-final@example.test")
    ai_original = generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    ai_draft = {**ai_original["draft"], "overall_assessment": "AI ORIGINAL ONLY COMMENT SHOULD NOT APPEAR"}
    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE ai_supervisor_review_drafts SET draft_json = ? WHERE draft_id = ?",
            (json.dumps(ai_draft, ensure_ascii=False), ai_original["draft_id"]),
        )
        connection.commit()
    finally:
        connection.close()
    saved_comment = "Please clarify the evaluation metrics and baseline comparison."
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(
            supervisor_profile["supervisor_id"],
            comments=saved_comment,
            suffix=" Saved",
        ),
    )
    assert saved.status_code == 200
    assert saved.json()["supervisor_comments"] == saved_comment

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "SUPERVISOR COMMENTS" in text
    assert saved_comment in text
    assert "AI ORIGINAL ONLY COMMENT SHOULD NOT APPEAR" not in text


def test_final_feedback_pdf_omits_empty_supervisor_comments_heading(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "empty-comments-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], comments=""),
    )
    assert saved.status_code == 200
    assert saved.json()["supervisor_comments"] is None

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "SUPERVISOR COMMENTS" not in text
    assert "null" not in text
    assert "undefined" not in text


def test_final_feedback_pdf_reads_supervisor_comments_after_client_refresh(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "refresh-comments@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved_comment = "Persisted comment after refresh.\nSecond line remains readable in the final PDF."
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(
            supervisor_profile["supervisor_id"],
            comments=saved_comment,
            suffix=" Refresh",
        ),
    )
    assert saved.status_code == 200

    refreshed_app = FastAPI()
    refreshed_app.include_router(supervisor.router)

    def override_connection():
        return connect(database_path)

    refreshed_app.dependency_overrides[get_db_connection] = override_connection
    refreshed_client = TestClient(refreshed_app)
    loaded = refreshed_client.get(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        params={"analysis_id": "A1", "supervisor_id": supervisor_profile["supervisor_id"]},
    )
    response = final_pdf(refreshed_client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert loaded.status_code == 200
    assert loaded.json()["supervisor_comments"] == saved_comment
    assert response.status_code == 200
    text = pdf_text(response)
    assert "SUPERVISOR COMMENTS" in text
    assert "Persisted comment after refresh." in text
    assert "Second line remains readable in the final PDF." in text


def test_final_feedback_pdf_handles_long_supervisor_comments(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "long-comments@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    long_comment = "Please expand the evaluation justification and baseline comparison. " * 40
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(
            supervisor_profile["supervisor_id"],
            comments=long_comment,
            suffix=" Long Comment",
        ),
    )
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert b"/Type /Page" in response.content
    text = pdf_text(response)
    assert "SUPERVISOR COMMENTS" in text
    assert "Please expand the evaluation justification and baseline comparison." in text


def test_final_feedback_pdf_requires_saved_supervisor_review(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "no-saved-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "Save the supervisor review before generating the final feedback PDF."


def test_final_feedback_pdf_rejects_wrong_analysis_version_link(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "wrong-final-link@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")

    response = final_pdf(client, versions[0]["version_id"], "A2", supervisor_profile["supervisor_id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "This analysis_id is not linked to the requested proposal version."


def test_final_feedback_pdf_rejects_unassigned_supervisor(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    assigned = create_assigned_supervisor(database_path, proposal["student_id"], "assigned-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(assigned["supervisor_id"]),
    )
    assert saved.status_code == 200
    connection = connect(database_path)
    try:
        user = create_user(connection, email="unassigned-final@example.test", role="supervisor", display_name="Unassigned Supervisor")
        unassigned = create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
    finally:
        connection.close()

    response = final_pdf(client, versions[0]["version_id"], "A1", unassigned["supervisor_id"])

    assert response.status_code == 403
    assert response.json()["detail"] == "Supervisor is not assigned to this proposal's student."


def test_final_feedback_pdf_supports_v1_without_v2_and_long_saved_content(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=1)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "long-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    payload = edited_payload(supervisor_profile["supervisor_id"])
    payload["overall_assessment"] = "Long supervisor assessment. " * 120
    payload["strengths"] = ["Detailed saved strength. " * 40]
    payload["areas_requiring_improvement"] = ["Detailed saved improvement. " * 40]
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert b"/Type /Page" in response.content


def test_final_feedback_pdf_does_not_modify_model_score_records(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "scores-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200
    before = list_grading_history()

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    after = list_grading_history()
    assert after == before


def test_final_feedback_pdf_does_not_present_model_scores_or_status_labels(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "no-score-presentation@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    grading_records = list_grading_history()
    grading_records[0]["score_label"] = "Very Strong"
    grading_records[0]["model_status"] = "baseline"
    grading_records[0]["submission_readiness"] = {"status": "Minor Revision Required"}
    grading_records[0]["final_readiness"] = {"percentage": 91, "label": "Ready for Supervisor Review"}
    replace_grading_history(grading_records)
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "SUPERVISOR-APPROVED FEEDBACK" in text
    assert "Analysis Evidence Snapshot" not in text
    assert "Semantic Score" not in text
    assert "Semantic Percentage" not in text
    assert "Semantic Label" not in text
    assert "Predicted Score" not in text
    assert "Final Readiness" not in text
    assert "Model Classification" not in text
    assert "Model Status" not in text
    assert "Classification Reason" not in text
    assert "Incomplete Proposal" not in text
    assert "Needs Revision" not in text
    assert "Minor Revision Required" not in text
    assert "Ready for Supervisor Review" not in text
    assert "Very Strong" not in text
    assert "baseline" not in text


def test_final_feedback_pdf_preserves_supervisor_sections_and_structure_support(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "sections-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], suffix=" Section"),
    )
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "Student Information" in text
    assert "Proposal Information" in text
    assert "1. Overall Assessment" in text
    assert "2. Strengths" in text
    assert "3. Areas Requiring Improvement" in text
    assert "4. Methodology Feedback" in text
    assert "5. Evaluation / Validation Feedback" in text
    assert "6. Recommendations" in text
    assert "7. Suggested Revision Instructions" in text
    assert "REVISION ACTION PLAN" in text
    assert "PROPOSAL STRUCTURE" in text
    assert "Completeness" in text
    assert "Sections Still Requiring Attention" in text
    assert "Evaluation" in text
    assert "LEARNING SUPPORT / RECOMMENDED RESOURCES" in text
    assert "Research Methods Guide" in text
    assert "REPORT NOTE" in text


def test_final_feedback_pdf_includes_clickable_resource_links(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "resource-links@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Writing Measurable Research Objectives",
            "description": "Useful for strengthening research objectives and aligning them with the problem.",
            "url": "https://example.test/objectives",
            "category": "Objectives",
        }
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    draft = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    assert draft.status_code == 201
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(
            supervisor_profile["supervisor_id"],
            comments="Please clarify the evaluation metrics and baseline comparison.",
        ),
    )
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_extracted_text(response)
    assert "Writing Measurable Research Objectives" in text
    assert "Useful for strengthening research objectives" in text
    assert "Open Resource" in text
    assert "No learning resources were available for this analysis." not in text
    assert pdf_uri_annotations(response) == ["https://example.test/objectives"]
    assert "Please clarify the evaluation metrics and baseline comparison." in text


def test_final_feedback_pdf_does_not_fabricate_resource_links(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "resource-no-link@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Library-only Objectives Worksheet",
            "description": "A local worksheet without an external URL.",
            "category": "Objectives",
        }
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    draft = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    assert draft.status_code == 201
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_extracted_text(response)
    assert "Library-only Objectives Worksheet" in text
    assert "Resource link unavailable" in text
    assert "https://example.test" not in text
    assert pdf_uri_annotations(response) == []


def test_legacy_review_draft_recovers_resources_only_from_linked_analysis(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "legacy-v4@example.test")
    v4_record = analysis_history_record("A_V4")
    v4_record["recommended_resources"] = [
        {
            "id": "v4-methods",
            "title": "Selecting Data Collection Methods",
            "description": "Guidance for choosing suitable qualitative and quantitative collection methods.",
            "url": "https://example.test/v4-data-collection",
            "category": "Data Collection",
            "reason": "The linked V4 analysis identified data collection as the related area.",
            "relevance_score": 0.85,
        }
    ]
    v4_record["retrieved_feedback"] = [{"comment_text": "V4 feedback about data collection."}]
    other_record = analysis_history_record("A_OTHER")
    other_record["recommended_resources"] = [
        {
            "title": "Unrelated Resource Must Not Leak",
            "description": "Belongs to a different analysis/version.",
            "url": "https://example.test/other-analysis",
            "category": "Evaluation",
        }
    ]
    write_custom_histories(
        analysis_path,
        grading_path,
        [v4_record, other_record],
        [grading_history_record("A_V4"), grading_history_record("A_OTHER")],
    )
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A_V4")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A_OTHER")
    generated = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A_V4"})
    assert generated.status_code == 201

    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE ai_supervisor_review_drafts SET evidence_json = ? WHERE draft_id = ?",
            (
                json.dumps(
                    {
                        "proposal_text_used": True,
                        "analysis_used": True,
                        "analysis_id": "A_V4",
                        "recommended_resource_titles": [],
                    },
                    ensure_ascii=False,
                ),
                generated.json()["draft_id"],
            ),
        )
        connection.commit()
    finally:
        connection.close()

    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A_V4"),
    )
    response = final_pdf(client, versions[0]["version_id"], "A_V4", supervisor_profile["supervisor_id"])

    assert saved.status_code == 200
    assert response.status_code == 200
    text = pdf_extracted_text(response)
    assert "Selecting Data Collection Methods" in text
    assert "Related Area:" in text
    assert "Data Collection" in text
    assert "linked V4 analysis identified data collection" in text
    assert "Unrelated Resource Must Not Leak" not in text
    assert "No learning resources were available for this analysis." not in text
    assert pdf_uri_annotations(response) == ["https://example.test/v4-data-collection"]


def test_final_feedback_pdf_keeps_distinct_resource_urls_and_ignores_invalid_urls(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "multi-url@example.test")
    analysis_record = analysis_history_record("A_URLS")
    analysis_record["recommended_resources"] = [
        {
            "title": "Methodology Resource",
            "description": "Methodology guidance.",
            "url": "https://example.test/methodology",
            "category": "Methodology",
        },
        {
            "title": "Evaluation Resource",
            "description": "Evaluation guidance.",
            "url": "http://example.test/evaluation",
            "category": "Evaluation",
        },
        {
            "title": "Invalid Resource",
            "description": "Should not become a link.",
            "url": "javascript:alert(1)",
            "category": "Security",
        },
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A_URLS")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A_URLS")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A_URLS"}).status_code == 201
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A_URLS"),
    )
    response = final_pdf(client, versions[0]["version_id"], "A_URLS", supervisor_profile["supervisor_id"])

    assert saved.status_code == 200
    assert response.status_code == 200
    text = pdf_extracted_text(response)
    assert "Methodology Resource" in text
    assert "Evaluation Resource" in text
    assert "Invalid Resource" in text
    assert "Resource link unavailable" in text
    uris = pdf_uri_annotations(response)
    assert "https://example.test/methodology" in uris
    assert "http://example.test/evaluation" in uris
    assert "javascript:alert(1)" not in uris


def test_final_feedback_pdf_shows_empty_state_when_no_resource_evidence_exists(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "empty-resource@example.test")
    analysis_record = analysis_history_record("A_EMPTY")
    analysis_record["recommended_resources"] = []
    analysis_record["retrieved_feedback"] = []
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A_EMPTY")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A_EMPTY")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A_EMPTY"}).status_code == 201
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A_EMPTY"),
    )
    response = final_pdf(client, versions[0]["version_id"], "A_EMPTY", supervisor_profile["supervisor_id"])

    assert saved.status_code == 200
    assert response.status_code == 200
    assert "No learning resources were available for this analysis." in pdf_extracted_text(response)
    assert pdf_uri_annotations(response) == []


def test_final_feedback_pdf_action_plan_uses_missing_sections_and_supervisor_revision_guidance(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "action-plan@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Writing Measurable Research Objectives",
            "description": "Supports the student in defining clear, measurable research objectives.",
            "url": "https://example.test/objectives",
            "category": "Objectives",
        }
    ]
    grading_record = grading_history_record("A1")
    grading_record["proposal_completeness"] = {"percentage": 75, "missing_sections": ["Objectives"]}
    grading_record["missing_sections"] = ["Objectives"]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_record])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    draft = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    assert draft.status_code == 201
    payload = edited_payload(supervisor_profile["supervisor_id"])
    payload["suggested_revision_instructions"] = [
        "Improve Objectives by making each objective measurable and aligned with the research problem."
    ]
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "REVISION ACTION PLAN" in text
    assert "Add / Improve Research Objectives" in text
    assert "What to change:" in text
    assert "Improve Objectives by making each objective measurable" in text
    assert "Recommended support:" in text
    assert "Writing Measurable Research Objectives" in text
    assert "https://example.test/objectives" in pdf_uri_annotations(response)


def test_final_feedback_pdf_consolidates_duplicate_literature_review_actions(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "dedupe-lit@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Building a Critical Literature Review",
            "description": "Techniques for synthesizing prior research, identifying gaps, and positioning a study.",
            "url": "https://example.test/literature",
            "category": "Literature Review",
        }
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"}).status_code == 201
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="")
    payload["areas_requiring_improvement"] = [
        "The literature review could benefit from a more critical analysis of existing systems and their limitations."
    ]
    payload["recommendations"] = [
        "Enhance the literature review by incorporating a more critical perspective on existing tools and their shortcomings."
    ]
    payload["suggested_revision_instructions"] = [
        "Revise the literature review to include a critical analysis of existing systems and their limitations."
    ]
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    action_plan = text_between(text, "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert action_plan.count("Strengthen the Literature Review") == 1
    assert "Building a Critical Literature Review" in action_plan
    assert "https://example.test/literature" in pdf_uri_annotations(response)


def test_final_feedback_pdf_keeps_distinct_consolidated_actions(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "distinct-actions@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="")
    payload["areas_requiring_improvement"] = [
        "The literature review needs a more critical comparison of previous systems.",
        "The methodology should explain the implementation process and component interaction.",
        "The evaluation strategy should define metrics and validation procedures.",
    ]
    payload["recommendations"] = []
    payload["suggested_revision_instructions"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    action_plan = text_between(pdf_text(response), "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert "Strengthen the Literature Review" in action_plan
    assert "Clarify the Methodology" in action_plan
    assert "Develop the Evaluation Strategy" in action_plan


def test_final_feedback_pdf_does_not_turn_non_actionable_comment_into_task(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "non-action-comment@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="good")
    payload["areas_requiring_improvement"] = []
    payload["recommendations"] = []
    payload["suggested_revision_instructions"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    action_plan = text_between(text, "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert "SUPERVISOR COMMENTS" in text
    assert "good" in text
    assert "Respond to Supervisor Comments" not in action_plan
    assert "What to change: good" not in action_plan


def test_final_feedback_pdf_supports_actionable_supervisor_comment(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "action-comment@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    payload = edited_payload(
        supervisor_profile["supervisor_id"],
        comments="Add a baseline comparison to the evaluation section.",
    )
    payload["areas_requiring_improvement"] = []
    payload["recommendations"] = []
    payload["suggested_revision_instructions"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    action_plan = text_between(text, "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert "Develop the Evaluation Strategy" in action_plan
    assert "Add a baseline comparison to the evaluation section." in text


def test_final_feedback_pdf_deduplicates_missing_objectives_action(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "dedupe-objectives@example.test")
    grading_record = grading_history_record("A1")
    grading_record["proposal_completeness"] = {"percentage": 75, "missing_sections": ["Objectives"]}
    grading_record["missing_sections"] = ["Objectives"]
    write_custom_histories(analysis_path, grading_path, [analysis_history_record("A1")], [grading_record])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"}).status_code == 201
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="")
    payload["suggested_revision_instructions"] = ["Add clear research objectives."]
    payload["areas_requiring_improvement"] = ["The objectives section is missing and should be added."]
    payload["recommendations"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    action_plan = text_between(pdf_text(response), "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert action_plan.count("Add / Improve Research Objectives") == 1


def test_final_feedback_pdf_matches_resources_to_related_action_items(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "resource-match-actions@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Building a Critical Literature Review",
            "description": "Techniques for synthesizing prior research.",
            "url": "https://example.test/lit",
            "category": "Literature Review",
        },
        {
            "title": "Designing a Reproducible Methodology",
            "description": "Guidance on research design and transparent procedures.",
            "url": "https://example.test/method",
            "category": "Methodology",
        },
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"}).status_code == 201
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="")
    payload["areas_requiring_improvement"] = [
        "The literature review needs critical synthesis.",
        "The methodology needs clearer research design details.",
    ]
    payload["recommendations"] = []
    payload["suggested_revision_instructions"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    action_plan = text_between(text, "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    assert "Strengthen the Literature Review" in action_plan
    assert "Building a Critical Literature Review" in action_plan
    assert "Clarify the Methodology" in action_plan
    assert "Designing a Reproducible Methodology" in action_plan
    assert "https://example.test/lit" in pdf_uri_annotations(response)
    assert "https://example.test/method" in pdf_uri_annotations(response)


def test_final_feedback_pdf_does_not_attach_unrelated_resource_to_action(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "no-fake-action-resource@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Building a Critical Literature Review",
            "description": "Techniques for synthesizing prior research.",
            "url": "https://example.test/lit",
            "category": "Literature Review",
        }
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    assert client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"}).status_code == 201
    payload = edited_payload(supervisor_profile["supervisor_id"], comments="")
    payload["areas_requiring_improvement"] = ["The evaluation strategy should define metrics and validation procedures."]
    payload["recommendations"] = []
    payload["suggested_revision_instructions"] = []
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    action_plan = text_between(text, "REVISION ACTION PLAN", "PROPOSAL STRUCTURE")
    learning_support = text_between(text, "LEARNING SUPPORT / RECOMMENDED RESOURCES", "REPORT NOTE")
    assert "Develop the Evaluation Strategy" in action_plan
    assert "Building a Critical Literature Review" not in action_plan
    assert "Building a Critical Literature Review" in learning_support
    assert "https://example.test/lit" in pdf_uri_annotations(response)


def test_final_feedback_pdf_reduces_technical_ids_and_formats_dates(draft_client):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "dates-final@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200
    raw_updated_at = saved.json()["updated_at"]

    response = final_pdf(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    text = pdf_text(response)
    assert "Analysis ID" not in text
    assert raw_updated_at not in text
    assert "Review Date" in text
    assert "Report Generated" in text
    assert "UTC" in text


def test_send_feedback_emails_supervisor_approved_pdf_and_logs_delivery(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-success@example.test")
    analysis_record = analysis_history_record("A1")
    analysis_record["recommended_resources"] = [
        {
            "title": "Writing Measurable Research Objectives",
            "description": "Useful for strengthening measurable objectives.",
            "url": "https://example.test/objectives",
            "category": "Objectives",
        }
    ]
    write_custom_histories(analysis_path, grading_path, [analysis_record], [grading_history_record("A1")])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    ai_response = client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    assert ai_response.status_code == 201
    ai_original = ai_response.json()
    original_draft = {**ai_original["draft"], "methodology_feedback": "AI ORIGINAL METHODOLOGY"}
    connection = connect(database_path)
    try:
        connection.execute(
            "UPDATE ai_supervisor_review_drafts SET draft_json = ? WHERE draft_id = ?",
            (json.dumps(original_draft, ensure_ascii=False), ai_original["draft_id"]),
        )
        connection.commit()
    finally:
        connection.close()
    payload = edited_payload(supervisor_profile["supervisor_id"])
    payload["methodology_feedback"] = "SUPERVISOR APPROVED METHODOLOGY"
    saved = client.put(f"/versions/{versions[0]['version_id']}/supervisor-review-draft", json=payload)
    assert saved.status_code == 200
    sent_messages = []

    def fake_send(**kwargs):
        sent_messages.append(kwargs)
        return "resend_msg_success"

    monkeypatch.setattr(email_service, "send_feedback_email", fake_send)

    response = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 200
    delivery = response.json()
    assert delivery["status"] == "SENT"
    assert delivery["provider_name"] == "resend"
    assert delivery["provider_message_id"] == "resend_msg_success"
    assert delivery["report_reference"].endswith(".pdf")
    assert delivery["recipient_email"] == "student@example.test"
    assert delivery["version_id"] == versions[0]["version_id"]
    assert delivery["analysis_id"] == "A1"
    assert len(sent_messages) == 1
    assert sent_messages[0]["recipient_email"] == "student@example.test"
    attachment = sent_messages[0]["attachments"][0]
    text = attachment.content.decode("latin-1", errors="ignore")
    assert attachment.content_type == "application/pdf"
    assert attachment.content.startswith(b"%PDF")
    assert "SUPERVISOR APPROVED METHODOLOGY" in text
    assert "AI ORIGINAL METHODOLOGY" not in text
    assert "Supervisor Final Feedback Report" in text
    assert "Writing Measurable Research Objectives" in text
    assert "https://example.test/objectives" in pdf_uri_annotations(type("AttachmentResponse", (), {"content": attachment.content})())
    assert "Semantic Score" not in text
    assert "Final Readiness" not in text
    assert "Model Classification" not in text

    refreshed = delivery_state(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "SENT"


def test_send_feedback_requires_student_email(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path)
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-no-email@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200
    monkeypatch.setattr(email_service, "send_feedback_email", lambda **kwargs: pytest.fail("email should not send"))

    response = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 422
    assert response.json()["detail"] == "Student email is not available."


def test_send_feedback_requires_saved_supervisor_review(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-no-review@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    monkeypatch.setattr(email_service, "send_feedback_email", lambda **kwargs: pytest.fail("email should not send"))

    response = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "Save the supervisor review before generating the final feedback PDF."


def test_send_feedback_rejects_wrong_analysis_link_and_unassigned_supervisor(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-link@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    client.post(f"/versions/{versions[0]['version_id']}/review-draft", json={"analysis_id": "A1"})
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1"),
    )
    assert saved.status_code == 200
    monkeypatch.setattr(email_service, "send_feedback_email", lambda **kwargs: pytest.fail("email should not send"))
    connection = connect(database_path)
    try:
        user = create_user(connection, email="send-unassigned@example.test", role="supervisor", display_name="Unassigned")
        unassigned = create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
    finally:
        connection.close()

    wrong_analysis = send_feedback(client, versions[0]["version_id"], "A2", supervisor_profile["supervisor_id"])
    unassigned_response = send_feedback(client, versions[0]["version_id"], "A1", unassigned["supervisor_id"])

    assert wrong_analysis.status_code == 409
    assert wrong_analysis.json()["detail"] == "This analysis_id is not linked to the requested proposal version."
    assert unassigned_response.status_code == 403
    assert unassigned_response.json()["detail"] == "Supervisor is not assigned to this proposal's student."


def test_send_feedback_logs_failed_provider_response_and_allows_retry(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-failure@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200
    calls = {"count": 0}

    def flaky_send(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise email_service.EmailDeliveryError("SMTP rejected recipient")
        return "resend_msg_retry"

    monkeypatch.setattr(email_service, "send_feedback_email", flaky_send)

    failed = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])
    retry = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert failed.status_code == 502
    assert failed.json()["detail"] == "SMTP rejected recipient"
    assert retry.status_code == 200
    assert retry.json()["status"] == "SENT"
    assert calls["count"] == 2
    connection = connect(database_path)
    try:
        statuses = [
            row["status"]
            for row in connection.execute(
                "SELECT status FROM notification_logs WHERE version_id = ? AND analysis_id = ? ORDER BY created_at",
                (versions[0]["version_id"], "A1"),
            ).fetchall()
        ]
    finally:
        connection.close()
    assert statuses == ["FAILED", "SENT"]


def test_send_feedback_blocks_duplicate_success_and_keeps_version_analysis_isolation(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=2, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-duplicate@example.test")
    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], versions[0]["version_id"], "A1")
    link_analysis(database_path, proposal["proposal_id"], versions[1]["version_id"], "A2")
    for version, analysis_id in [(versions[0], "A1"), (versions[1], "A2")]:
        assert client.post(f"/versions/{version['version_id']}/review-draft", json={"analysis_id": analysis_id}).status_code == 201
        assert client.put(
            f"/versions/{version['version_id']}/supervisor-review-draft",
            json=edited_payload(supervisor_profile["supervisor_id"], analysis_id=analysis_id, suffix=f" {analysis_id}"),
        ).status_code == 200
    sent_messages = []
    def fake_duplicate_send(**kwargs):
        sent_messages.append(kwargs)
        return f"resend_msg_{len(sent_messages)}"

    monkeypatch.setattr(email_service, "send_feedback_email", fake_duplicate_send)

    first = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])
    duplicate = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])
    v2_state_before = delivery_state(client, versions[1]["version_id"], "A2", supervisor_profile["supervisor_id"])
    second_version = send_feedback(client, versions[1]["version_id"], "A2", supervisor_profile["supervisor_id"])

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert "already sent" in duplicate.json()["detail"]
    assert v2_state_before.status_code == 200
    assert v2_state_before.json()["status"] == "NOT_SENT"
    assert second_version.status_code == 200
    assert second_version.json()["version_id"] == versions[1]["version_id"]
    assert len(sent_messages) == 2


def test_send_feedback_reports_unconfigured_email_without_marking_sent(draft_client, monkeypatch):
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="student@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "send-unconfigured@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0])
    saved = client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"]),
    )
    assert saved.status_code == 200
    monkeypatch.setattr(
        email_service,
        "send_feedback_email",
        lambda **kwargs: (_ for _ in ()).throw(email_service.EmailDeliveryNotConfigured("Email delivery is not configured.")),
    )

    response = send_feedback(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])
    state = delivery_state(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 503
    assert response.json()["detail"] == "Email delivery is not configured."
    assert state.status_code == 200
    assert state.json()["status"] == "FAILED"


def test_complete_review_records_reviewed_without_creating_revision(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="complete@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "complete-review@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1", comments="Approved final review."),
    ).status_code == 200

    response = review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "COMPLETE_REVIEW")
    state = get_review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"])

    assert response.status_code == 201
    assert response.json()["status"] == "COMPLETE"
    assert response.json()["decision"] == "REVIEWED"
    assert state.status_code == 200
    assert state.json()["status"] == "COMPLETE"
    connection = connect(database_path)
    try:
        assert len(repositories.get_proposal_versions(connection, proposal["proposal_id"])) == 1
        assert repositories.get_latest_supervisor_review(
            connection,
            version_id=versions[0]["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )["decision"] == "REVIEWED"
    finally:
        connection.close()


def test_request_revision_records_revision_without_creating_v2(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="revision@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "request-revision@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1", comments="Please revise methodology."),
    ).status_code == 200

    response = review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION")

    assert response.status_code == 201
    assert response.json()["status"] == "REVISION_REQUESTED"
    assert response.json()["decision"] == "REQUEST_REVISION"
    connection = connect(database_path)
    try:
        versions_after = repositories.get_proposal_versions(connection, proposal["proposal_id"])
        assert len(versions_after) == 1
        assert repositories.get_latest_supervisor_review(
            connection,
            version_id=versions[0]["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )["decision"] == "REVISION_REQUESTED"
    finally:
        connection.close()


def test_revision_requested_allows_next_version_and_preserves_v1_analysis(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="next-version@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "next-version@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1"),
    ).status_code == 200
    assert review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION").status_code == 201

    revised = create_revised_version(
        client,
        proposal["proposal_id"],
        supervisor_profile["supervisor_id"],
        filename="draft-v2.pdf",
        extracted_text="Abstract Revised proposal. Introduction Revised context.",
    )

    assert revised.status_code == 201
    assert revised.json()["version_number"] == 2
    connection = connect(database_path)
    try:
        versions_after = repositories.get_proposal_versions(connection, proposal["proposal_id"])
        assert [version["version_number"] for version in versions_after] == [1, 2]
        assert repositories.get_version_analyses(connection, versions[0]["version_id"])[0]["analysis_id"] == "A1"
        assert repositories.get_version_analyses(connection, revised.json()["version_id"]) == []
        assert repositories.get_proposal(connection, proposal["proposal_id"])["current_version_id"] == revised.json()["version_id"]
    finally:
        connection.close()


def test_v2_can_be_analyzed_and_completed_independently_from_v1(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="v2-complete@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "v2-complete@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1"),
    ).status_code == 200
    assert review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION").status_code == 201
    revised = create_revised_version(client, proposal["proposal_id"], supervisor_profile["supervisor_id"]).json()

    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], revised["version_id"], "A2")
    assert client.post(f"/versions/{revised['version_id']}/review-draft", json={"analysis_id": "A2"}).status_code == 201
    assert client.put(
        f"/versions/{revised['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A2", suffix=" V2"),
    ).status_code == 200
    completed = review_outcome(client, revised["version_id"], "A2", supervisor_profile["supervisor_id"], "COMPLETE_REVIEW")

    assert completed.status_code == 201
    assert completed.json()["status"] == "COMPLETE"
    connection = connect(database_path)
    try:
        v1_review = repositories.get_latest_supervisor_review(
            connection,
            version_id=versions[0]["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )
        v2_review = repositories.get_latest_supervisor_review(
            connection,
            version_id=revised["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )
        assert v1_review["decision"] == "REVISION_REQUESTED"
        assert v2_review["decision"] == "REVIEWED"
        assert repositories.get_version_analyses(connection, versions[0]["version_id"])[0]["analysis_id"] == "A1"
        assert repositories.get_version_analyses(connection, revised["version_id"])[0]["analysis_id"] == "A2"
    finally:
        connection.close()


def test_v1_to_v2_to_v3_lifecycle_is_version_scoped_and_v3_can_complete(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="v3-cycle@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "v3-cycle@example.test")

    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1", suffix=" V1"),
    ).status_code == 200
    assert review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION").status_code == 201

    v2 = create_revised_version(
        client,
        proposal["proposal_id"],
        supervisor_profile["supervisor_id"],
        filename="draft-v2.pdf",
        extracted_text="Abstract Revised V2. Introduction Revised V2.",
    ).json()
    assert v2["version_number"] == 2
    assert client.get(f"/versions/{v2['version_id']}/analyses").json() == []
    assert client.get(f"/versions/{v2['version_id']}/supervisor-reviews").json() == []

    write_histories(analysis_path, grading_path, ["A1", "A2"])
    link_analysis(database_path, proposal["proposal_id"], v2["version_id"], "A2")
    assert client.post(f"/versions/{v2['version_id']}/review-draft", json={"analysis_id": "A2"}).status_code == 201
    assert client.put(
        f"/versions/{v2['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A2", suffix=" V2"),
    ).status_code == 200
    assert review_outcome(client, v2["version_id"], "A2", supervisor_profile["supervisor_id"], "REQUEST_REVISION").status_code == 201

    v3 = create_revised_version(
        client,
        proposal["proposal_id"],
        supervisor_profile["supervisor_id"],
        filename="draft-v3.pdf",
        extracted_text="Abstract Revised V3. Introduction Revised V3.",
    ).json()
    assert v3["version_number"] == 3
    assert client.get(f"/versions/{v3['version_id']}/analyses").json() == []
    assert client.get(f"/versions/{v3['version_id']}/supervisor-reviews").json() == []

    write_histories(analysis_path, grading_path, ["A1", "A2", "A3"])
    link_analysis(database_path, proposal["proposal_id"], v3["version_id"], "A3")
    assert client.post(f"/versions/{v3['version_id']}/review-draft", json={"analysis_id": "A3"}).status_code == 201
    assert client.put(
        f"/versions/{v3['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A3", suffix=" V3", comments="Complete at V3."),
    ).status_code == 200
    completed = review_outcome(client, v3["version_id"], "A3", supervisor_profile["supervisor_id"], "COMPLETE_REVIEW")

    assert completed.status_code == 201
    assert completed.json()["status"] == "COMPLETE"
    no_v4 = create_revised_version(client, proposal["proposal_id"], supervisor_profile["supervisor_id"], filename="draft-v4.pdf")
    assert no_v4.status_code == 409
    connection = connect(database_path)
    try:
        versions_after = repositories.get_proposal_versions(connection, proposal["proposal_id"])
        assert [version["version_number"] for version in versions_after] == [1, 2, 3]
        assert repositories.get_proposal(connection, proposal["proposal_id"])["current_version_id"] == v3["version_id"]
        assert [row["analysis_id"] for row in repositories.get_version_analyses(connection, versions[0]["version_id"])] == ["A1"]
        assert [row["analysis_id"] for row in repositories.get_version_analyses(connection, v2["version_id"])] == ["A2"]
        assert [row["analysis_id"] for row in repositories.get_version_analyses(connection, v3["version_id"])] == ["A3"]
        assert repositories.get_latest_supervisor_review(
            connection,
            version_id=versions[0]["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )["decision"] == "REVISION_REQUESTED"
        assert repositories.get_latest_supervisor_review(
            connection,
            version_id=v2["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )["decision"] == "REVISION_REQUESTED"
        assert repositories.get_latest_supervisor_review(
            connection,
            version_id=v3["version_id"],
            supervisor_id=supervisor_profile["supervisor_id"],
        )["decision"] == "REVIEWED"
    finally:
        connection.close()


def test_revision_chain_creates_v4_only_after_v3_revision_request(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, version_count=3, student_email="v4@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "v4-chain@example.test")
    write_histories(analysis_path, grading_path, ["A3"])
    link_analysis(database_path, proposal["proposal_id"], versions[2]["version_id"], "A3")
    assert client.post(f"/versions/{versions[2]['version_id']}/review-draft", json={"analysis_id": "A3"}).status_code == 201
    assert client.put(
        f"/versions/{versions[2]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A3", suffix=" V3"),
    ).status_code == 200
    assert review_outcome(client, versions[2]["version_id"], "A3", supervisor_profile["supervisor_id"], "REQUEST_REVISION").status_code == 201

    revised = create_revised_version(client, proposal["proposal_id"], supervisor_profile["supervisor_id"], filename="draft-v4.pdf")

    assert revised.status_code == 201
    assert revised.json()["version_number"] == 4
    connection = connect(database_path)
    try:
        assert [version["version_number"] for version in repositories.get_proposal_versions(connection, proposal["proposal_id"])] == [1, 2, 3, 4]
    finally:
        connection.close()


def test_unassigned_supervisor_cannot_record_outcome_or_create_revision(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="assigned-only@example.test")
    assigned = create_assigned_supervisor(database_path, proposal["student_id"], "assigned-only@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(assigned["supervisor_id"], analysis_id="A1"),
    ).status_code == 200
    assert review_outcome(client, versions[0]["version_id"], "A1", assigned["supervisor_id"], "REQUEST_REVISION").status_code == 201
    connection = connect(database_path)
    try:
        user = create_user(connection, email="unassigned-outcome@example.test", role="supervisor", display_name="Unassigned")
        unassigned = create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
    finally:
        connection.close()

    outcome = review_outcome(client, versions[0]["version_id"], "A1", unassigned["supervisor_id"], "COMPLETE_REVIEW")
    revision = create_revised_version(client, proposal["proposal_id"], unassigned["supervisor_id"])

    assert outcome.status_code == 403
    assert revision.status_code == 403


def test_review_outcome_blocks_conflicting_decision_and_duplicate_revision_upload(draft_client, monkeypatch):
    monkeypatch.setattr(email_service, "is_configured", lambda: False)
    client, database_path, analysis_path, grading_path, _ = draft_client
    proposal, versions = create_proposal_fixture(database_path, student_email="duplicate-outcome@example.test")
    supervisor_profile = create_assigned_supervisor(database_path, proposal["student_id"], "duplicate-outcome@example.test")
    generate_ai_draft_for_linked_version(client, database_path, analysis_path, grading_path, proposal, versions[0], "A1")
    assert client.put(
        f"/versions/{versions[0]['version_id']}/supervisor-review-draft",
        json=edited_payload(supervisor_profile["supervisor_id"], analysis_id="A1"),
    ).status_code == 200

    first = review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION")
    duplicate = review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "REQUEST_REVISION")
    conflicting = review_outcome(client, versions[0]["version_id"], "A1", supervisor_profile["supervisor_id"], "COMPLETE_REVIEW")
    revised = create_revised_version(client, proposal["proposal_id"], supervisor_profile["supervisor_id"], filename="draft-v2.pdf")
    duplicate_revision = create_revised_version(client, proposal["proposal_id"], supervisor_profile["supervisor_id"], filename="draft-v2-copy.pdf")

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["review_id"] == first.json()["review_id"]
    assert conflicting.status_code == 409
    assert revised.status_code == 201
    assert duplicate_revision.status_code == 409
    connection = connect(database_path)
    try:
        review_count = connection.execute(
            "SELECT COUNT(*) FROM supervisor_reviews WHERE version_id = ? AND supervisor_id = ?",
            (versions[0]["version_id"], supervisor_profile["supervisor_id"]),
        ).fetchone()[0]
        assert review_count == 1
        assert [version["version_number"] for version in repositories.get_proposal_versions(connection, proposal["proposal_id"])] == [1, 2]
    finally:
        connection.close()
