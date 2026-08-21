from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.get("/grading-history", response_model=HistoryResponse)
def get_grading_history() -> HistoryResponse:
    """Return the newest baseline semantic grading records."""
    history = load_grading_history()
    analysis_index = build_analysis_history_index()
    newest_first = []
    for record in reversed(history):
        if not isinstance(record, dict):
            continue
        score = max(0.0, min(float(GRADING_MAX_SCORE), float(record.get("predicted_score", 0))))
        percentage = max(0.0, min(100.0, float(record.get("percentage_score", percentage_from_score(score)))))
        completeness_payload = normalize_completeness_payload(
            record.get("proposal_completeness"),
            linked_analysis_text_for_grading(record, analysis_index),
        )
        readiness_payload = record.get("submission_readiness")
        if completeness_payload:
            readiness_payload = readiness_for_completeness(float(completeness_payload.get("percentage", 0))).model_dump()
        else:
            readiness_payload = None
        final_readiness = normalize_final_readiness_payload(record, round(percentage, 1), completeness_payload)
        semantic_label = score_label(percentage)
        final_assessment = normalize_final_proposal_assessment_semantic_label(
            record.get("final_proposal_assessment"),
            round(percentage, 1),
            semantic_label,
        )
        newest_first.append(
            {
                **record,
                "predicted_score": round(score, 2),
                "max_score": int(record.get("max_score", GRADING_MAX_SCORE)),
                "percentage_score": round(percentage, 1),
                "semantic_percentage": round(percentage, 1),
                "semantic_label": semantic_label,
                "score_label": semantic_label,
                "model_status": record.get("model_status", "baseline"),
                "proposal_completeness": completeness_payload,
                "completeness_percentage": completeness_payload.get("percentage") if completeness_payload else None,
                "final_readiness": final_readiness,
                "final_readiness_percentage": final_readiness.get("percentage") if isinstance(final_readiness, dict) else None,
                "final_readiness_label": final_readiness.get("label") if isinstance(final_readiness, dict) else None,
                "missing_sections": completeness_payload.get("missing_sections", []) if completeness_payload else [],
                "submission_readiness": readiness_payload,
                "submission_status": readiness_payload.get("status") if isinstance(readiness_payload, dict) else "Not Available",
                "submission_reason": readiness_payload.get("reason") if isinstance(readiness_payload, dict) else legacy_completeness_unavailable_reason(),
                "final_proposal_assessment": final_assessment,
                "warning": record.get("warning", GRADING_WARNING),
            }
        )
    return HistoryResponse(total=len(history), items=newest_first[:50])

@router.delete("/grading-history")
def clear_grading_history() -> dict[str, str]:
    """Clear all saved semantic grading records."""
    write_grading_history([])
    return {"message": "Semantic grading history cleared"}

@router.get("/analysis-history", response_model=HistoryResponse)
def get_analysis_history() -> HistoryResponse:
    """Return the newest saved analyses from real successful /analyze calls."""
    history = load_analysis_history()
    newest_first = [
        effective_analysis_record(record) if isinstance(record, dict) else record
        for record in reversed(history)
    ]
    return HistoryResponse(total=len(history), items=newest_first[:50])

@router.delete("/analysis-history/{analysis_id}")
def delete_analysis_history_record(analysis_id: str) -> dict[str, Any]:
    """Delete one saved analysis history record by ID."""
    deleted = delete_analysis_record_by_id(analysis_id)
    return {
        "message": "Analysis history record deleted",
        "deleted_id": deleted.get("id"),
    }

@router.delete("/analysis-history")
def clear_analysis_history() -> dict[str, str]:
    """Clear all saved analysis records."""
    write_analysis_history([])
    return {"message": "Analysis history cleared"}