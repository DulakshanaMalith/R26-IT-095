from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.post("/review", response_model=ReviewEndpointResponse)
def run_autonomous_review(payload: ReviewRequest) -> ReviewEndpointResponse:
    """Run autonomous LLM review on the provided proposal."""
    cleaned_text = clean_text(payload.proposal_text)
    validate_research_proposal_text(cleaned_text)
    
    try:
        review, metadata = run_review(
            proposal_text=cleaned_text,
            mode=payload.mode,
            excluded_author_ids=payload.excluded_author_ids,
            top_k=payload.top_k
        )
        return ReviewEndpointResponse(review=review, metadata=metadata)
    except Exception as e:
        logger.error(f"LLM Review failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Autonomous review failed: {e}"
        )