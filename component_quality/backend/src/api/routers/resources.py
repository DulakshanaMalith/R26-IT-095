from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.post("/recommend-resources", response_model=ResourceResponse)
def recommend_learning_resources(payload: ResourceRequest) -> ResourceResponse:
    """Recommend academic learning resources for the supplied weakness."""
    cleaned_text = clean_text(payload.text)
    validation = validate_research_proposal_text(cleaned_text, payload.analysis_id)
    text = prepare_model_text(cleaned_text)
    feedback = payload.feedback.strip()
    resources = get_recommended_resources(text, feedback, missing_sections=validation.missing_sections, top_k=3)
    return ResourceResponse(resources=resources)