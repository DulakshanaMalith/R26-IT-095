import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.routers import analysis
from src.api.services import core_logic


def test_analyze_returns_complete_recommended_resource_objects(tmp_path, monkeypatch):

    monkeypatch.setattr(analysis, "validate_research_proposal_text", lambda text, analysis_id=None: type("Validation", (), {"missing_sections": [], "detected_sections": []})())
    monkeypatch.setattr(analysis, "predict_tag", lambda request, text: "Weakness")
    monkeypatch.setattr(analysis, "analysis_tag_from_validation", lambda tag, validation: (tag, "Needs clearer methodology."))
    monkeypatch.setattr(analysis, "retrieve_feedback", lambda text, top_k=3: [{"comment_text": "Clarify the method."}])
    resource = {
        "id": "methods-guide",
        "title": "Research Methods Guide",
        "description": "Guidance for choosing a suitable academic research method.",
        "url": "https://example.test/research-methods",
        "category": "Methodology",
        "reason": "The proposal needs stronger method design.",
        "relevance_score": 0.85,
    }
    monkeypatch.setattr(
        analysis,
        "get_recommended_resources",
        lambda text, feedback_context, missing_sections=None, learning_needs=None, top_k=3: [resource],
    )

    app = FastAPI()
    app.include_router(analysis.router)
    response = TestClient(app).post(
        "/analyze",
        json={
            "analysis_id": "A_RESOURCE",
            "text": "Abstract This research proposal investigates feedback. Methodology The study uses document analysis.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_resources"] == [resource]
    assert payload["retrieved_feedback"] == [{"comment_text": "Clarify the method."}]
