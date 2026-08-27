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
    
    learning_needs = payload.learning_needs
    if not learning_needs:
        _, _, _, sections_evidence, _ = calculate_sufficiency_aware_completeness(cleaned_text, validation.detected_sections, validation.missing_sections)
        learning_needs = build_learning_needs(validation.missing_sections, sections_evidence)
        
    text = prepare_model_text(cleaned_text)
    feedback = payload.feedback.strip()
    resources = get_recommended_resources(text, feedback, missing_sections=validation.missing_sections, learning_needs=learning_needs, top_k=3)
    return ResourceResponse(resources=resources)