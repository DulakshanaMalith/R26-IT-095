from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import asyncio
import hashlib
from fastapi.concurrency import run_in_threadpool
from cachetools import TTLCache

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from src.api.auth import get_current_supervisor
from src.api.database import get_db_connection
from src.api.schemas import (
    AnalysisResponse,
    AssignmentResponse,
    CreateAssignmentRequest,
    CreateProposalRequest,
    CreateRevisedProposalVersionRequest,
    CreateProposalVersionRequest,
    CreateStudentRequest,
    GradeReportResponse,
    KnowledgeGraphResponse,
    LinkVersionAnalysisRequest,
    ProposalResponse,
    ProposalVersionResponse,
    FeedbackDeliveryResponse,
    ReviewOutcomeRequest,
    ReviewOutcomeResponse,
    SaveSupervisorEditedReviewDraftRequest,
    SendFeedbackRequest,
    SupervisorEditedReviewDraftResponse,
    SupervisorReviewDraftContent,
    SupervisorReviewDraftRequest,
    SupervisorReviewDraftResponse,
    SupervisorDashboardResponse,
    SupervisorReviewRequest,
    SupervisorReviewResponse,
    StudentResponse,
    SupervisorStudentResponse,
    UpdateStudentEmailRequest,
    VersionAnalysisResponse,
    ValidatedRetrievedFeedbackList,
)
from src.api.services import core_logic
from src.api.services import resend_service as email_service
from src.api.services.improvement_tracking import build_proposal_improvement
from src.core import knowledge_graph
from src.db import repositories
from src.reviewer.providers import get_llm_provider
from src.reviewer.service import run_review

router = APIRouter(tags=["supervisors"])
logger = logging.getLogger(__name__)

_analysis_locks: dict[str, asyncio.Lock] = {}
_analysis_cache = TTLCache(maxsize=100, ttl=300)


def _close_connection(connection: Any) -> None:
    connection.close()


def _constraint_error(exc: IntegrityError) -> HTTPException:
    message = str(exc).lower()
    if "students.academic_student_id" in message:
        detail = "A student with this academic student ID already exists."
    elif "uq_active_primary_supervisor_per_student" in message:
        detail = "This student already has an active primary supervisor."
    elif "uq_active_supervisor_student_role" in message:
        detail = "This active supervisor/student assignment already exists."
    elif "foreign key" in message:
        detail = "Referenced supervisor, student, proposal, version, or review does not exist."
    elif "check constraint" in message:
        detail = "The request contains an unsupported role, decision, type, or status value."
    else:
        detail = "Database constraint failed."
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _require_record(record: dict[str, Any] | None, detail: str) -> dict[str, Any]:
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return record


def _next_version_number(connection: Any, proposal_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM proposal_versions WHERE proposal_id = ?",
        (proposal_id,),
    ).fetchone()
    return int(row["next_version"])


def _version_text(version: dict[str, Any]) -> str:
    edited_text = version.get("edited_text")
    if isinstance(edited_text, str) and edited_text.strip():
        return edited_text
    extracted_text = version.get("extracted_text")
    if isinstance(extracted_text, str) and extracted_text.strip():
        return extracted_text
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Proposal version does not contain usable proposal text.",
    )


def _proposal_version_response(version: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(version)
    return sanitized


def _storage_decision(decision: str) -> str:
    return "REVISION_REQUESTED" if decision == "REQUEST_REVISION" else decision


def _api_decision(decision: str) -> str:
    return "REQUEST_REVISION" if decision == "REVISION_REQUESTED" else decision


def _outcome_storage_decision(decision: str) -> str:
    return "REVIEWED" if decision == "COMPLETE_REVIEW" else "REVISION_REQUESTED"


def _outcome_status(decision: str | None) -> str:
    if decision == "REVIEWED":
        return "COMPLETE"
    if decision == "REVISION_REQUESTED":
        return "REVISION_REQUESTED"
    return "AWAITING_SUPERVISOR_DECISION"


def _outcome_label(status_value: str) -> str:
    labels = {
        "COMPLETE": "Complete",
        "REVISION_REQUESTED": "Revision Requested",
        "AWAITING_SUPERVISOR_DECISION": "Awaiting Supervisor Decision",
    }
    return labels.get(status_value, "Awaiting Supervisor Decision")


def _review_response(review: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(review)
    normalized["decision"] = _api_decision(str(normalized["decision"]))
    normalized["comments"] = normalized.pop("overall_comment", None)
    return normalized


def _review_outcome_response(
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    storage_decision = str(review.get("decision")) if review else None
    if storage_decision not in {"REVIEWED", "REVISION_REQUESTED"}:
        storage_decision = None
    status_value = _outcome_status(storage_decision)
    return {
        "review_id": review.get("review_id") if review and storage_decision else None,
        "version_id": version_id,
        "analysis_id": analysis_id,
        "supervisor_id": supervisor_id,
        "decision": _api_decision(storage_decision) if storage_decision else None,
        "status": status_value,
        "label": _outcome_label(status_value),
        "comments": review.get("overall_comment") if review and storage_decision else None,
        "created_at": review.get("created_at") if review and storage_decision else None,
        "updated_at": review.get("updated_at") if review and storage_decision else None,
    }


def _json_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _json_evidence(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    return _json_payload(record.get("evidence_json"))


def _draft_response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_id": record["draft_id"],
        "proposal_id": record["proposal_id"],
        "version_id": record["version_id"],
        "analysis_id": record["analysis_id"],
        "draft": _json_payload(record.get("draft_json")),
        "evidence_summary": _json_payload(record.get("evidence_json")),
        "llm_metadata": _json_payload(record.get("llm_metadata_json")),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    return []


def _evidence_list(record: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            return list(value)
    return []


def _edited_review_draft_response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": record["review_id"],
        "version_id": record["version_id"],
        "analysis_id": record["analysis_id"],
        "supervisor_id": record["supervisor_id"],
        "ai_draft_id": record["ai_draft_id"],
        "draft": {
            "overall_assessment": record["overall_assessment"],
            "strengths": _json_list(record.get("strengths_json")),
            "areas_requiring_improvement": _json_list(record.get("areas_requiring_improvement_json")),
            "methodology_feedback": record["methodology_feedback"],
            "evaluation_validation_feedback": record["evaluation_validation_feedback"],
            "recommendations": _json_list(record.get("recommendations_json")),
            "suggested_revision_instructions": _json_list(record.get("suggested_revision_instructions_json")),
        },
        "supervisor_comments": record.get("supervisor_comments"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def _delivery_response(
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    student_id: str,
    record: dict[str, Any] | None = None,
    recipient_email: str | None = None,
) -> dict[str, Any]:
    if record is None:
        return {
            "notification_id": None,
            "version_id": version_id,
            "analysis_id": analysis_id,
            "supervisor_id": supervisor_id,
            "student_id": student_id,
            "recipient_email": recipient_email,
            "subject": None,
            "status": "NOT_SENT",
            "notification_type": "FEEDBACK_SENT",
            "created_at": None,
            "sent_at": None,
            "error_message": None,
            "provider_name": None,
            "provider_message_id": None,
            "report_reference": None,
        }
    return {
        "notification_id": record["notification_id"],
        "version_id": record["version_id"],
        "analysis_id": record.get("analysis_id") or analysis_id,
        "supervisor_id": record.get("supervisor_id") or supervisor_id,
        "student_id": record["student_id"],
        "recipient_email": record.get("recipient_email"),
        "subject": record.get("subject"),
        "status": record["status"],
        "notification_type": record["notification_type"],
        "created_at": record["created_at"],
        "sent_at": record.get("sent_at"),
        "error_message": record.get("error_message"),
        "provider_name": record.get("provider_name"),
        "provider_message_id": record.get("provider_message_id"),
        "report_reference": record.get("report_reference"),
    }


def _feedback_email_subject(proposal: dict[str, Any], version: dict[str, Any]) -> str:
    title = str(proposal.get("title") or "Proposal").strip()
    version_label = f"V{version.get('version_number') or 'current'}"
    return f"ResearchPilot Proposal Feedback - {title} - {version_label}"


def _feedback_email_body(student: dict[str, Any], proposal: dict[str, Any], version: dict[str, Any]) -> str:
    student_name = str(student.get("full_name") or "Student").strip()
    proposal_title = str(proposal.get("title") or "Proposal").strip()
    version_label = f"V{version.get('version_number') or 'current'}"
    return (
        f"Hello {student_name},\n\n"
        "Your supervisor has reviewed your proposal submission.\n\n"
        f"Proposal: {proposal_title}\n"
        f"Version: {version_label}\n\n"
        "Please review the attached supervisor feedback report and use the recommendations "
        "when preparing your next revision.\n\n"
        "Regards,\n"
        "ResearchPilot\n"
    )


def _safe_delivery_error(exc: Exception) -> str:
    message = str(exc).strip() or "Email delivery failed."
    return message[:500]


def _final_feedback_artifacts(
    connection: Any,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str, bytes]:
    version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
    proposal = _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
    student = _require_record(repositories.get_student(connection, proposal["student_id"]), "Student not found.")
    analysis = _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
    ai_draft = _require_record(
        repositories.get_ai_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
        ),
        "AI supervisor review draft not found.",
    )
    saved_review = repositories.get_supervisor_review_draft(
        connection,
        version_id=version_id,
        analysis_id=analysis_id,
        supervisor_id=supervisor_id,
    )
    if saved_review is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Save the supervisor review before generating the final feedback PDF.",
        )

    evidence = _review_draft_evidence(proposal=proposal, version=version, analysis_id=analysis_id)
    saved_evidence = _json_evidence(ai_draft)
    if saved_evidence:
        repaired_evidence = dict(saved_evidence)
        for key in ("retrieved_feedback", "recommended_resources"):
            if not repaired_evidence.get(key):
                repaired_evidence[key] = evidence.get(key, [])
        repaired_evidence.setdefault("analysis_id", analysis_id)
        repaired_evidence.setdefault("proposal_title", evidence.get("proposal_title"))
        repaired_evidence.setdefault("version_number", evidence.get("version_number"))
        repaired_evidence.setdefault("semantic_grade", evidence.get("semantic_grade", {}))
        repaired_evidence.setdefault("knowledge_graph", evidence.get("knowledge_graph", {}))
        evidence = repaired_evidence
        logger.info(
            "Recovered final-feedback resource evidence: version_id=%s analysis_id=%s saved_resources=%s linked_resources=%s",
            version_id,
            analysis_id,
            len(saved_evidence.get("recommended_resources") or []),
            len(evidence.get("recommended_resources") or []),
        )
    filename, pdf_bytes = core_logic.generate_supervisor_final_feedback_pdf(
        student=student,
        proposal=proposal,
        version=version,
        analysis=analysis,
        supervisor_review=_edited_review_draft_response(saved_review),
        evidence=evidence,
    )
    return version, proposal, student, analysis, saved_review, filename, pdf_bytes


def _review_outcome_artifacts(
    connection: Any,
    *,
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    require_saved_feedback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
    proposal = _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
    _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
    _require_record(
        repositories.get_ai_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
        ),
        "AI supervisor review draft not found.",
    )
    saved_review = repositories.get_supervisor_review_draft(
        connection,
        version_id=version_id,
        analysis_id=analysis_id,
        supervisor_id=supervisor_id,
    )
    if saved_review is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Save the supervisor review before recording the review outcome.",
        )
    if require_saved_feedback and email_service.is_configured():
        sent_feedback = repositories.get_successful_feedback_delivery(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            supervisor_review_draft_id=saved_review["review_id"],
        )
        if sent_feedback is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Send the final feedback before recording the review outcome.",
            )
    return version, proposal, saved_review, repositories.get_latest_supervisor_review(
        connection,
        version_id=version_id,
        supervisor_id=supervisor_id,
    )


def _current_proposal_version(connection: Any, proposal: dict[str, Any]) -> dict[str, Any] | None:
    current_version_id = proposal.get("current_version_id")
    if current_version_id:
        return repositories.get_proposal_version(connection, current_version_id)
    versions = repositories.get_proposal_versions(connection, proposal["proposal_id"])
    return versions[-1] if versions else None


def _linked_analysis_for_version(
    connection: Any,
    *,
    version_id: str,
    analysis_id: str,
) -> dict[str, Any]:
    linked = repositories.get_analysis(connection, analysis_id)
    if linked is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analyze this proposal version before generating a supervisor review draft.",
        )
    if linked["version_id"] != version_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This analysis_id is not linked to the requested proposal version.",
        )
    return linked


def _require_supervisor_for_version(
    connection: Any,
    *,
    version: dict[str, Any],
    supervisor_id: str,
) -> dict[str, Any]:
    proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
    _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
    if not repositories.supervisor_is_assigned_to_student(
        connection,
        supervisor_id=supervisor_id,
        student_id=proposal["student_id"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor is not assigned to this proposal's student.",
        )
    return proposal


def _find_grading_record_by_analysis_id_read_only(analysis_id: str) -> dict[str, Any] | None:
    return core_logic.find_grading_record_by_analysis_id(analysis_id)


def _find_graph_record_by_analysis_id_read_only(analysis_id: str) -> dict[str, Any] | None:
    return knowledge_graph.find_graph_record_by_analysis_id(analysis_id)


def _review_draft_evidence(
    *,
    proposal: dict[str, Any],
    version: dict[str, Any],
    analysis_id: str,
) -> dict[str, Any]:
    analysis_record = core_logic.find_analysis_record_by_id(analysis_id)
    if analysis_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completed Analyzer analysis was not found.")
    grading_record = _find_grading_record_by_analysis_id_read_only(analysis_id)
    graph_record = _find_graph_record_by_analysis_id_read_only(analysis_id)
    effective_analysis = core_logic.effective_analysis_record(analysis_record)
    proposal_text = (
        version.get("edited_text")
        or version.get("extracted_text")
        or effective_analysis.get("input_text")
        or ""
    )
    if not isinstance(proposal_text, str) or not proposal_text.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Analysis evidence does not contain proposal text for review draft generation.",
        )

    return {
        "proposal_title": proposal.get("title"),
        "version_number": version.get("version_number"),
        "analysis_id": analysis_id,
        "proposal_text": proposal_text,
        "predicted_tag": effective_analysis.get("predicted_tag"),
        "classification_reason": effective_analysis.get("classification_reason"),
        "retrieved_feedback": _evidence_list(effective_analysis, "retrieved_feedback", "feedback"),
        "recommended_resources": _evidence_list(
            effective_analysis,
            "recommended_resources",
            "resources",
            "recommendations",
        ),
        "semantic_grade": {
            "predicted_score": grading_record.get("predicted_score") if grading_record else None,
            "max_score": grading_record.get("max_score") if grading_record else None,
            "percentage_score": grading_record.get("percentage_score") if grading_record else None,
            "score_label": grading_record.get("score_label") or grading_record.get("label") if grading_record else None,
            "section_scores": grading_record.get("section_scores", {}) if grading_record else {},
            "proposal_completeness": grading_record.get("proposal_completeness") if grading_record else None,
            "submission_readiness": grading_record.get("submission_readiness") if grading_record else None,
            "final_readiness": grading_record.get("final_readiness") if grading_record else None,
            "final_proposal_assessment": grading_record.get("final_proposal_assessment") if grading_record else None,
            "missing_sections": grading_record.get("missing_sections", []) if grading_record else [],
        },
        "knowledge_graph": {
            "concepts": graph_record.get("concepts", []) if graph_record else [],
            "edges": graph_record.get("edges", []) if graph_record else [],
            "missing_concepts": graph_record.get("missing_concepts", []) if graph_record else [],
        },
    }


def generate_structured_supervisor_review_draft(evidence: dict[str, Any]) -> tuple[SupervisorReviewDraftContent, dict[str, Any]]:
    system_prompt = (
        "You generate structured academic supervisor review drafts from existing ResearchPilot evidence. "
        "Use only the proposal content and supplied analysis evidence. Do not invent, recalculate, or alter "
        "semantic scores, completeness scores, final readiness, section scores, or model predictions. "
        "The current proposal text is the absolute source of truth. "
        "Use the 'autonomous_review_findings' as your PRIMARY source for strengths and weaknesses. "
        "Before recommending an addition (e.g., metrics, comparisons, guardian feedback, privacy, methodology), rigorously check if the proposal already contains it. "
        "Never recommend adding something that already exists. If the element exists but lacks detail, specifically request elaboration on that existing element."
    )
    prompt_evidence = dict(evidence)
    prompt_evidence["proposal_text"] = str(prompt_evidence.get("proposal_text", ""))[:24000]
    user_prompt = (
        "Create a structured supervisor review draft for this analyzed proposal version. "
        "Return concise, specific feedback connected to the evidence. Required sections: "
        "overall_assessment, strengths, areas_requiring_improvement, methodology_feedback, "
        "evaluation_validation_feedback, recommendations, suggested_revision_instructions.\n\n"
        f"EVIDENCE JSON:\n{json.dumps(prompt_evidence, ensure_ascii=False, indent=2)}"
    )
    provider = get_llm_provider()
    draft, metadata = provider.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=SupervisorReviewDraftContent,
    )
    return draft, metadata


def validate_retrieved_feedback_evidence(evidence: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    system_prompt = (
        "You validate historical retrieved feedback against a newly uploaded proposal. "
        "Historical feedback may mention technologies or requirements that do not apply to the new proposal. "
        "Filter and rewrite the feedback to keep only concepts supported by the new proposal text."
    )
    
    proposal_text = str(evidence.get("proposal_text", ""))[:24000]
    retrieved_feedback = evidence.get("retrieved_feedback", [])
    
    if not retrieved_feedback:
        return evidence, {"skipped": True, "reason": "No retrieved feedback"}
        
    feedback_strings = [
        f"Item {i}: {fb.get('comment_text', '')}"
        for i, fb in enumerate(retrieved_feedback)
    ]
    
    user_prompt = (
        "Evaluate the following historical feedback items against the provided proposal text.\n"
        "For each item, classify if it is supported, partially supported, or unsupported by the proposal.\n"
        "If partially supported, provide a rewritten 'validated_feedback' that removes unsupported claims (e.g. if feedback mentions cameras but proposal only uses microphones, remove camera references).\n"
        "If unsupported, set 'validated_feedback' to null.\n\n"
        f"PROPOSAL TEXT (Truncated):\n{proposal_text}\n\n"
        f"HISTORICAL FEEDBACK ITEMS:\n" + "\n".join(feedback_strings)
    )
    
    provider = get_llm_provider()
    try:
        validated_list, metadata = provider.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ValidatedRetrievedFeedbackList,
        )
        
        validated_evidence = dict(evidence)
        new_feedback_list = []
        for i, item in enumerate(validated_list.items):
            if item.is_supported and item.validated_feedback:
                original_fb = retrieved_feedback[i] if i < len(retrieved_feedback) else {}
                new_fb = dict(original_fb)
                new_fb["comment_text"] = item.validated_feedback
                new_feedback_list.append(new_fb)
        
        validated_evidence["retrieved_feedback"] = new_feedback_list
        return validated_evidence, {"validated_list": validated_list.model_dump(), "llm_metadata": metadata}
    except Exception as exc:
        validated_evidence = dict(evidence)
        validated_evidence["retrieved_feedback"] = []
        return validated_evidence, {"error": str(exc)}


def validate_structured_supervisor_review_draft(raw_draft: SupervisorReviewDraftContent, evidence: dict[str, Any]) -> tuple[SupervisorReviewDraftContent, dict[str, Any]]:
    system_prompt = (
        "You are a strict evidence-grounding validator for academic reviews. "
        "Ensure every substantive criticism and recommendation is factually supported by the proposal. "
        "Distinguish between 'missing' and 'present_but_needs_detail'. "
        "If an element (e.g. comparison, metrics, guardian feedback, methodology, privacy) is present, do not claim it is missing; instead request clarification if needed. "
        "Remove or rewrite statements containing unsupported proposal-specific claims (e.g. hallucinated technologies like cameras if absent). "
        "Ensure strengths and weaknesses do not contradict each other. "
        "Before recommending an addition, verify whether the proposal already contains it. Never recommend adding something that already exists."
    )
    
    proposal_text = str(evidence.get("proposal_text", ""))[:24000]
    
    user_prompt = (
        "Validate the following AI-generated supervisor review draft against the proposal text.\n"
        "Apply sentence-level grounding. Rewrite or remove any unsupported sentences.\n\n"
        f"PROPOSAL TEXT (Truncated):\n{proposal_text}\n\n"
        f"RAW REVIEW DRAFT:\n{raw_draft.model_dump_json(indent=2)}"
    )
    
    provider = get_llm_provider()
    try:
        validated_draft, metadata = provider.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=SupervisorReviewDraftContent,
        )
        return validated_draft, {"llm_metadata": metadata}
    except Exception as exc:
        raise ValueError(f"Draft validation failed: {exc}")



def _build_analysis_response(record: dict[str, Any], text: str) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_id=core_logic.record_analysis_id(record) or record["id"],
        request_id=record.get("request_id"),
        input_text=text,
        predicted_tag=record.get("predicted_tag", "Not available"),
        model_predicted_tag=record.get("model_predicted_tag"),
        classification_reason=record.get("classification_reason"),
        retrieved_feedback=record.get("retrieved_feedback", []),
        recommended_resources=record.get("recommended_resources", []),
        student_name=record.get("student_name"),
        student_id=record.get("student_id"),
        proposal_title=record.get("proposal_title"),
    )


def _run_version_analysis_pipeline(
    *,
    request: Request,
    version: dict[str, Any],
    proposal: dict[str, Any],
    student: dict[str, Any] | None,
    analysis_id: str,
) -> dict[str, Any]:
    import time
    t0 = time.time()
    text = core_logic.clean_text(_version_text(version))
    validation = core_logic.validate_research_proposal_text(text, analysis_id)
    t1 = time.time(); logger.info(f"[TIMER] validation took {t1 - t0:.3f}s")
    
    model_text = core_logic.prepare_model_text(text)
    model_predicted_tag = core_logic.predict_tag(request, model_text)
    predicted_tag, classification_reason = core_logic.analysis_tag_from_validation(model_predicted_tag, validation)
    t2 = time.time(); logger.info(f"[TIMER] predict_tag took {t2 - t1:.3f}s")
    
    feedback_matches = core_logic.retrieve_feedback(model_text, top_k=3)
    t3 = time.time(); logger.info(f"[TIMER] retrieve_feedback took {t3 - t2:.3f}s")
    
    feedback_context = " ".join(str(match.get("comment_text", "")) for match in feedback_matches)
    resources = core_logic.get_recommended_resources(model_text, feedback_context, missing_sections=validation.missing_sections, top_k=3)
    t4 = time.time(); logger.info(f"[TIMER] get_recommended_resources took {t4 - t3:.3f}s")
    
    source = version.get("source_type")
    filename = version.get("original_filename")
    student_name = student.get("full_name") if student else None
    academic_student_id = student.get("academic_student_id") if student else None

    analysis_record = core_logic.save_analysis_record(
        analysis_id=analysis_id,
        request_id=analysis_id,
        text=text,
        predicted_tag=predicted_tag,
        model_predicted_tag=model_predicted_tag,
        classification_reason=classification_reason,
        feedback_matches=feedback_matches,
        resources=resources,
        source=source,
        filename=filename,
        student_name=student_name,
        student_id=academic_student_id,
        proposal_title=proposal.get("title"),
    )

    prepared_grade_text = core_logic.prepare_model_text(text, max_chars=50000)
    word_count = len(prepared_grade_text.split())
    raw_score = core_logic.grade_report_text(prepared_grade_text)
    t5 = time.time(); logger.info(f"[TIMER] grade_report_text took {t5 - t4:.3f}s")
    
    predicted_score = round(max(0.0, min(float(core_logic.GRADING_MAX_SCORE), raw_score)), 2)
    percentage_score = core_logic.percentage_from_score(predicted_score)
    label = core_logic.score_label(percentage_score)
    section_scores = core_logic.calculate_section_scores(prepared_grade_text)
    assessment = core_logic.build_final_proposal_assessment(
        text,
        predicted_score,
        percentage_score,
        label,
        validation=validation,
    )
    warning = (
        core_logic.GRADING_WARNING
        if word_count >= 300
        else f"{core_logic.GRADING_WARNING} {core_logic.SHORT_GRADING_WARNING}"
    )
    grading_record = core_logic.save_grading_record(
        analysis_id=analysis_id,
        source=source,
        filename=filename,
        input_text=text,
        word_count=word_count,
        predicted_score=predicted_score,
        percentage_score=percentage_score,
        label=label,
        section_scores=section_scores,
        proposal_completeness=assessment["proposal_completeness"],
        submission_readiness=assessment["submission_readiness"],
        final_proposal_assessment=assessment["final_proposal_assessment"],
        model_status="baseline",
        warning=warning,
    )

    graph_payload = None
    graph_error = None
    try:
        graph = core_logic.analyze_knowledge_graph(model_text)
        core_logic.save_graph_history(analysis_id=analysis_id, filename=filename, graph=graph)
        graph["analysis_id"] = analysis_id
        graph_payload = KnowledgeGraphResponse(**graph)
    except Exception as exc:  # Preserve Analyzer-style optional graph behavior.
        graph_error = str(exc)

    return {
        "text": text,
        "analysis": _build_analysis_response(analysis_record, text),
        "semantic_grade": GradeReportResponse(
            grading_id=grading_record["id"],
            analysis_id=grading_record.get("analysis_id"),
            predicted_score=predicted_score,
            max_score=core_logic.GRADING_MAX_SCORE,
            percentage_score=percentage_score,
            semantic_percentage=percentage_score,
            semantic_label=label,
            score_label=label,
            section_scores=section_scores,
            proposal_completeness=grading_record.get("proposal_completeness"),
            completeness_percentage=grading_record.get("completeness_percentage"),
            missing_sections=grading_record.get("missing_sections", []),
            submission_readiness=grading_record.get("submission_readiness"),
            submission_status=grading_record.get("submission_status"),
            submission_reason=grading_record.get("submission_reason"),
            final_proposal_assessment=grading_record.get("final_proposal_assessment"),
            final_readiness=grading_record.get("final_readiness"),
            final_readiness_percentage=grading_record.get("final_readiness_percentage"),
            final_readiness_label=grading_record.get("final_readiness_label"),
            model_status=grading_record["model_status"],
            warning=grading_record["warning"],
        ),
        "knowledge_graph": graph_payload,
        "knowledge_graph_error": graph_error,
    }


@router.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(payload: CreateStudentRequest, connection: Any = Depends(get_db_connection)) -> dict[str, Any]:
    try:
        return repositories.create_student(
            connection,
            academic_student_id=payload.academic_student_id,
            full_name=payload.full_name,
            email=payload.email,
            program=payload.program,
            cohort=payload.cohort,
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/me/students", response_model=list[SupervisorStudentResponse])
def get_current_supervisor_students(
    supervisor_profile: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> list[dict[str, Any]]:
    try:
        return repositories.get_supervisor_students(connection, supervisor_profile["supervisor_id"])
    finally:
        _close_connection(connection)


@router.get("/me/dashboard", response_model=SupervisorDashboardResponse)
def get_current_supervisor_dashboard(
    supervisor_profile: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        return repositories.get_supervisor_dashboard_summary(connection, supervisor_profile["supervisor_id"])
    finally:
        _close_connection(connection)


def _create_or_assign_student_to_supervisor(
    connection: Any,
    *,
    supervisor_id: str,
    payload: CreateStudentRequest,
) -> dict[str, Any]:
    student = repositories.get_student_by_academic_id(connection, payload.academic_student_id)
    if student is None:
        student = repositories.create_student(
            connection,
            academic_student_id=payload.academic_student_id,
            full_name=payload.full_name,
            email=payload.email,
            program=payload.program,
            cohort=payload.cohort,
        )
    elif not student.get("active"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This student record is inactive.")
    else:
        active_assignment = connection.execute(
            """
            SELECT 1
            FROM supervisor_student_assignments
            WHERE supervisor_id = ? AND student_id = ? AND active = 1
            LIMIT 1
            """,
            (supervisor_id, student["student_id"]),
        ).fetchone()
        if active_assignment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A student with this academic student ID already exists.",
            )
    repositories.assign_supervisor_to_student(
        connection,
        supervisor_id=supervisor_id,
        student_id=student["student_id"],
        assignment_role="primary_supervisor",
    )
    if student is not None and payload.email is not None:
        student = repositories.update_student_email(connection, student["student_id"], payload.email.strip() or None)
    return student


@router.post("/me/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_current_supervisor_student(
    payload: CreateStudentRequest,
    supervisor_profile: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        return _create_or_assign_student_to_supervisor(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            payload=payload,
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.delete("/me/students/{student_id}", response_model=AssignmentResponse)
def remove_current_supervisor_student(
    student_id: str,
    supervisor_profile: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        removed = repositories.remove_supervisor_student_assignment(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            student_id=student_id,
        )
        return _require_record(removed, "Supervisor/student assignment not found.")
    finally:
        _close_connection(connection)


@router.post("/supervisors/{supervisor_id}/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_supervisor_student(
    supervisor_id: str,
    payload: CreateStudentRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        return _create_or_assign_student_to_supervisor(
            connection,
            supervisor_id=supervisor_id,
            payload=payload,
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/students/{student_id}", response_model=StudentResponse)
def get_student(student_id: str, connection: Any = Depends(get_db_connection)) -> dict[str, Any]:
    try:
        return _require_record(repositories.get_student(connection, student_id), "Student not found.")
    finally:
        _close_connection(connection)


@router.patch("/students/{student_id}/email", response_model=StudentResponse)
def update_student_email(
    student_id: str,
    payload: UpdateStudentEmailRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        email = payload.email.strip() if payload.email else None
        if email:
            try:
                email_service.validate_email_address(email, field_name="student email")
            except email_service.InvalidRecipientEmail as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return _require_record(repositories.update_student_email(connection, student_id, email), "Student not found.")
    finally:
        _close_connection(connection)


@router.post(
    "/supervisors/{supervisor_id}/students/{student_id}/assign",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def assign_student_to_supervisor(
    supervisor_id: str,
    student_id: str,
    payload: CreateAssignmentRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        return repositories.assign_supervisor_to_student(
            connection,
            supervisor_id=supervisor_id,
            student_id=student_id,
            assignment_role=payload.assignment_role,
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.delete("/supervisors/{supervisor_id}/students/{student_id}", response_model=AssignmentResponse)
def remove_student_from_supervisor(
    supervisor_id: str,
    student_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        removed = repositories.remove_supervisor_student_assignment(
            connection,
            supervisor_id=supervisor_id,
            student_id=student_id,
        )
        return _require_record(removed, "Supervisor/student assignment not found.")
    finally:
        _close_connection(connection)


@router.get("/supervisors/{supervisor_id}/students", response_model=list[SupervisorStudentResponse])
def get_supervisor_students(supervisor_id: str, connection: Any = Depends(get_db_connection)) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        return repositories.get_supervisor_students(connection, supervisor_id)
    finally:
        _close_connection(connection)


@router.post("/students/{student_id}/proposals", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
def create_student_proposal(
    student_id: str,
    payload: CreateProposalRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        return repositories.create_proposal(connection, student_id=student_id, title=payload.title, status="DRAFT")
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/students/{student_id}/proposals", response_model=list[ProposalResponse])
def get_student_proposals(student_id: str, connection: Any = Depends(get_db_connection)) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_student(connection, student_id), "Student not found.")
        return repositories.get_student_proposals(connection, student_id)
    finally:
        _close_connection(connection)


@router.get("/proposals/{proposal_id}", response_model=ProposalResponse)
def get_proposal(proposal_id: str, connection: Any = Depends(get_db_connection)) -> dict[str, Any]:
    try:
        return _require_record(repositories.get_proposal(connection, proposal_id), "Proposal not found.")
    finally:
        _close_connection(connection)


@router.delete("/proposals/{proposal_id}")
def delete_proposal(
    proposal_id: str,
    supervisor_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        proposal = _require_record(repositories.get_proposal(connection, proposal_id), "Proposal not found.")
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        if not repositories.supervisor_is_assigned_to_student(
            connection,
            supervisor_id=supervisor_id,
            student_id=proposal["student_id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor is not assigned to this proposal's student.",
            )
        deleted = repositories.delete_proposal_tree(connection, proposal_id)
        return {
            "proposal_id": proposal_id,
            "student_id": proposal["student_id"],
            "deleted": deleted,
            "message": "Proposal workflow records deleted. Shared Analyzer history was preserved.",
        }
    finally:
        _close_connection(connection)


@router.get("/proposals/{proposal_id}/improvement")
def get_proposal_improvement(proposal_id: str, connection: Any = Depends(get_db_connection)) -> dict[str, Any]:
    try:
        return _require_record(build_proposal_improvement(connection, proposal_id), "Proposal not found.")
    finally:
        _close_connection(connection)


@router.post("/proposals/{proposal_id}/versions", response_model=ProposalVersionResponse, status_code=status.HTTP_201_CREATED)
def create_proposal_version(
    proposal_id: str,
    payload: CreateProposalVersionRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        _require_record(repositories.get_proposal(connection, proposal_id), "Proposal not found.")
        version = repositories.create_proposal_version(
            connection,
            proposal_id=proposal_id,
            version_number=_next_version_number(connection, proposal_id),
            original_filename=payload.original_filename,
            source_type=payload.source_type,
            extracted_text=payload.extracted_text,
            status="DRAFT",
        )
        return _proposal_version_response(version)
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.post("/proposals/{proposal_id}/revised-versions", response_model=ProposalVersionResponse, status_code=status.HTTP_201_CREATED)
def create_revised_proposal_version(
    proposal_id: str,
    payload: CreateRevisedProposalVersionRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        supervisor_id = payload.supervisor_id.strip()
        proposal = _require_record(repositories.get_proposal(connection, proposal_id), "Proposal not found.")
        _require_record(repositories.get_supervisor_profile(connection, supervisor_id), "Supervisor not found.")
        if not repositories.supervisor_is_assigned_to_student(
            connection,
            supervisor_id=supervisor_id,
            student_id=proposal["student_id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor is not assigned to this proposal's student.",
            )
        version = repositories.create_revised_proposal_version_after_revision_request(
            connection,
            proposal_id=proposal_id,
            supervisor_id=supervisor_id,
            original_filename=payload.original_filename,
            source_type=payload.source_type,
            extracted_text=payload.extracted_text,
            status="DRAFT",
        )
        return _proposal_version_response(version)
    except ValueError as exc:
        if str(exc) == "CURRENT_VERSION_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Create and review the first proposal version before uploading a revision.",
            ) from exc
        if str(exc) == "REVISION_NOT_REQUESTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Request revision on the current proposal version before uploading a revised proposal.",
            ) from exc
        raise
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/proposals/{proposal_id}/versions", response_model=list[ProposalVersionResponse])
def get_proposal_versions(proposal_id: str, connection: Any = Depends(get_db_connection)) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_proposal(connection, proposal_id), "Proposal not found.")
        return [_proposal_version_response(version) for version in repositories.get_proposal_versions(connection, proposal_id)]
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}", response_model=ProposalVersionResponse)
def get_version(version_id: str, connection: Any = Depends(get_db_connection)) -> dict[str, Any]:
    try:
        return _proposal_version_response(_require_record(repositories.get_proposal_version(connection, version_id), "Version not found."))
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/analyses")
def get_version_analyses(version_id: str, connection: Any = Depends(get_db_connection)) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        return repositories.get_version_analyses(connection, version_id)
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/gradings", response_model=list[GradeReportResponse])
def get_version_gradings(version_id: str, connection: Any = Depends(get_db_connection)) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        analyses = repositories.get_version_analyses(connection, version_id)
        gradings = []
        for analysis in analyses:
            grading = _find_grading_record_by_analysis_id_read_only(analysis["analysis_id"])
            if grading:
                gradings.append(grading)
        return gradings
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/review-draft", response_model=SupervisorReviewDraftResponse | None)
def get_version_review_draft(
    version_id: str,
    analysis_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any] | None:
    try:
        _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
        draft = repositories.get_ai_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
        )
        if not draft:
            return None
        return _draft_response(draft)
    finally:
        _close_connection(connection)


@router.post(
    "/versions/{version_id}/review-draft",
    response_model=SupervisorReviewDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_version_review_draft(
    version_id: str,
    payload: SupervisorReviewDraftRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        analysis_id = payload.analysis_id.strip()
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)

        existing = repositories.get_ai_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
        )
        if existing:
            return _draft_response(existing)

        evidence = _review_draft_evidence(proposal=proposal, version=version, analysis_id=analysis_id)
        
        try:
            autonomous_review, autonomous_review_metadata = run_review(
                proposal_text=evidence.get("proposal_text", ""),
                mode="llm_rag_criteria"
            )
            evidence["autonomous_review_findings"] = autonomous_review.model_dump()
        except Exception as exc:
            evidence["autonomous_review_findings"] = {"error": str(exc)}
            autonomous_review_metadata = {"error": str(exc)}
        
        # TEMPORARY: Skip retrieved feedback validation entirely
        validated_evidence = dict(evidence)
        feedback_validation_metadata = {"skipped": True, "reason": "Temporarily isolated to prevent RAG leakage"}
        
        print(f"\n[{analysis_id}] SUPERVISOR_PIPELINE_VERSION = 'GROUNDING_ISOLATION_V1'")
        print(f"[{analysis_id}] Evidence keys: {list(validated_evidence.keys())}")
        print(f"[{analysis_id}] retrieved_feedback exists: {'retrieved_feedback' in validated_evidence}")
        print(f"[{analysis_id}] recommended_resources exists: {'recommended_resources' in validated_evidence}")
        print(f"[{analysis_id}] autonomous_review_findings exists: {'autonomous_review_findings' in validated_evidence}\n")

        raw_draft, metadata = generate_structured_supervisor_review_draft(validated_evidence)
        validated_draft, draft_validation_metadata = validate_structured_supervisor_review_draft(raw_draft, validated_evidence)
        
        evidence_summary = {
            "proposal_text_used": True,
            "analysis_used": True,
            "semantic_rubric_used": bool(validated_evidence.get("semantic_grade")),
            "completeness_used": bool(validated_evidence.get("semantic_grade", {}).get("proposal_completeness")),
            "final_readiness_used": bool(validated_evidence.get("semantic_grade", {}).get("final_readiness")),
            "recommendations_used": bool(validated_evidence.get("recommended_resources")),
            "knowledge_gaps_used": bool(validated_evidence.get("knowledge_graph", {}).get("missing_concepts")),
            "predicted_tag": validated_evidence.get("predicted_tag"),
            "classification_reason": validated_evidence.get("classification_reason"),
            "retrieved_feedback_count": len(validated_evidence.get("retrieved_feedback") or []),
            "retrieved_feedback": list(validated_evidence.get("retrieved_feedback") or []),
            "recommended_resources": list(validated_evidence.get("recommended_resources") or []),
            "recommended_resource_titles": [
                resource.get("title")
                for resource in validated_evidence.get("recommended_resources") or []
                if isinstance(resource, dict) and resource.get("title")
            ],
            "missing_sections": validated_evidence.get("semantic_grade", {}).get("missing_sections", []),
            "proposal_completeness": validated_evidence.get("semantic_grade", {}).get("proposal_completeness"),
            "final_readiness": validated_evidence.get("semantic_grade", {}).get("final_readiness"),
        }
        
        metadata["raw_draft"] = raw_draft.model_dump()
        metadata["retrieved_feedback_validation"] = feedback_validation_metadata
        metadata["draft_validation"] = draft_validation_metadata
        metadata["autonomous_review_metadata"] = autonomous_review_metadata
        
        saved = repositories.create_ai_supervisor_review_draft(
            connection,
            proposal_id=proposal["proposal_id"],
            version_id=version_id,
            analysis_id=analysis_id,
            draft=validated_draft.model_dump(),
            evidence=evidence_summary,
            llm_metadata=metadata,
        )
        return _draft_response(saved)
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/supervisor-review-draft", response_model=SupervisorEditedReviewDraftResponse)
def get_supervisor_review_draft(
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
        _require_record(
            repositories.get_ai_supervisor_review_draft(
                connection,
                version_id=version_id,
                analysis_id=analysis_id,
            ),
            "AI supervisor review draft not found.",
        )
        draft = repositories.get_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
        )
        return _edited_review_draft_response(_require_record(draft, "Supervisor review draft not found."))
    finally:
        _close_connection(connection)


@router.put("/versions/{version_id}/supervisor-review-draft", response_model=SupervisorEditedReviewDraftResponse)
def save_supervisor_review_draft(
    version_id: str,
    payload: SaveSupervisorEditedReviewDraftRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        analysis_id = payload.analysis_id.strip()
        supervisor_id = payload.supervisor_id.strip()
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
        ai_draft = _require_record(
            repositories.get_ai_supervisor_review_draft(
                connection,
                version_id=version_id,
                analysis_id=analysis_id,
            ),
            "AI supervisor review draft not found.",
        )
        saved = repositories.save_supervisor_review_draft(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            ai_draft_id=ai_draft["draft_id"],
            overall_assessment=payload.overall_assessment.strip(),
            strengths=payload.strengths,
            areas_requiring_improvement=payload.areas_requiring_improvement,
            methodology_feedback=payload.methodology_feedback.strip(),
            evaluation_validation_feedback=payload.evaluation_validation_feedback.strip(),
            recommendations=payload.recommendations,
            suggested_revision_instructions=payload.suggested_revision_instructions,
            supervisor_comments=payload.supervisor_comments.strip() if payload.supervisor_comments else None,
        )
        return _edited_review_draft_response(saved)
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/final-feedback.pdf")
def generate_final_feedback_pdf(
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    connection: Any = Depends(get_db_connection),
) -> Response:
    try:
        _, _, _, _, _, filename, pdf_bytes = _final_feedback_artifacts(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/feedback-delivery", response_model=FeedbackDeliveryResponse)
def get_feedback_delivery(
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        proposal = _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
        student = _require_record(repositories.get_student(connection, proposal["student_id"]), "Student not found.")
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
        records = repositories.get_feedback_delivery_notifications(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
        )
        return _delivery_response(
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            student_id=student["student_id"],
            recipient_email=student.get("email"),
            record=records[0] if records else None,
        )
    finally:
        _close_connection(connection)


@router.post("/versions/{version_id}/send-feedback", response_model=FeedbackDeliveryResponse)
def send_feedback_to_student(
    version_id: str,
    payload: SendFeedbackRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        analysis_id = payload.analysis_id.strip()
        supervisor_id = payload.supervisor_id.strip()
        version, proposal, student, _, saved_review, filename, pdf_bytes = _final_feedback_artifacts(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
        )
        recipient_email = str(student.get("email") or "").strip()
        if not recipient_email:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Student email is not available.")
        try:
            email_service.validate_email_address(recipient_email, field_name="student email")
        except email_service.InvalidRecipientEmail as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if not pdf_bytes:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated feedback PDF was not found.")

        existing_sent = repositories.get_successful_feedback_delivery(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            supervisor_review_draft_id=saved_review["review_id"],
        )
        if existing_sent:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This feedback was already sent on {existing_sent.get('sent_at') or existing_sent.get('created_at')}.",
            )

        subject = _feedback_email_subject(proposal, version)
        body = _feedback_email_body(student, proposal, version)
        attempt = repositories.create_notification_log(
            connection,
            student_id=student["student_id"],
            proposal_id=proposal["proposal_id"],
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            supervisor_review_draft_id=saved_review["review_id"],
            recipient_email=recipient_email,
            subject=subject,
            notification_type="FEEDBACK_SENT",
            status="SENDING",
            provider_name="resend",
            report_reference=filename,
        )
        try:
            provider_message_id = email_service.send_feedback_email(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                attachments=[
                    email_service.EmailAttachment(
                        filename=filename,
                        content=pdf_bytes,
                    ),
                ],
            )
        except email_service.EmailDeliveryNotConfigured as exc:
            repositories.update_notification_log_status(
                connection,
                attempt["notification_id"],
                status="FAILED",
                error_message=_safe_delivery_error(exc),
                provider_name="resend",
                report_reference=filename,
            )
            logger.warning(
                "Feedback email configuration failure: version_id=%s analysis_id=%s supervisor_id=%s error_type=%s",
                version_id,
                analysis_id,
                supervisor_id,
                exc.__class__.__name__,
            )
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except email_service.EmailDeliveryError as exc:
            safe_detail = _safe_delivery_error(exc)
            repositories.update_notification_log_status(
                connection,
                attempt["notification_id"],
                status="FAILED",
                error_message=safe_detail,
                provider_name="resend",
                report_reference=filename,
            )
            logger.warning(
                "Feedback email delivery failure: version_id=%s analysis_id=%s supervisor_id=%s error_type=%s status_code=%s",
                version_id,
                analysis_id,
                supervisor_id,
                exc.__class__.__name__,
                getattr(exc, "status_code", None),
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=safe_detail) from exc

        sent = repositories.update_notification_log_status(
            connection,
            attempt["notification_id"],
            status="SENT",
            sent_at=datetime.now(timezone.utc).isoformat(),
            provider_name="resend",
            provider_message_id=provider_message_id,
            report_reference=filename,
        )
        return _delivery_response(
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            student_id=student["student_id"],
            record=sent,
        )
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/review-outcome", response_model=ReviewOutcomeResponse)
def get_review_outcome(
    version_id: str,
    analysis_id: str,
    supervisor_id: str,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        _require_supervisor_for_version(connection, version=version, supervisor_id=supervisor_id)
        _linked_analysis_for_version(connection, version_id=version_id, analysis_id=analysis_id)
        review = repositories.get_latest_supervisor_review(
            connection,
            version_id=version_id,
            supervisor_id=supervisor_id,
        )
        return _review_outcome_response(
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            review=review,
        )
    finally:
        _close_connection(connection)


@router.post("/versions/{version_id}/review-outcome", response_model=ReviewOutcomeResponse, status_code=status.HTTP_201_CREATED)
def save_review_outcome(
    version_id: str,
    payload: ReviewOutcomeRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        analysis_id = payload.analysis_id.strip()
        supervisor_id = payload.supervisor_id.strip()
        version, proposal, _, latest_review = _review_outcome_artifacts(
            connection,
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            require_saved_feedback=True,
        )
        decision = _outcome_storage_decision(payload.decision)
        comments = payload.comments.strip() if payload.comments else None
        if latest_review and latest_review.get("decision") in {"REVIEWED", "REVISION_REQUESTED"}:
            if latest_review["decision"] != decision:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This proposal version already has a final supervisor outcome.",
                )
            return _review_outcome_response(
                version_id=version_id,
                analysis_id=analysis_id,
                supervisor_id=supervisor_id,
                review=latest_review,
            )

        try:
            review = repositories.save_current_supervisor_review(
                connection,
                proposal_id=proposal["proposal_id"],
                version_id=version["version_id"],
                supervisor_id=supervisor_id,
                decision=decision,
                overall_comment=comments,
            )
        except IntegrityError:
            # Handle concurrent inserts race condition gracefully
            connection.rollback()
            pass

        enriched = repositories.get_latest_supervisor_review(
            connection,
            version_id=version_id,
            supervisor_id=supervisor_id,
        )
        return _review_outcome_response(
            version_id=version_id,
            analysis_id=analysis_id,
            supervisor_id=supervisor_id,
            review=enriched or review,
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.get("/versions/{version_id}/supervisor-reviews", response_model=list[SupervisorReviewResponse])
def get_version_supervisor_reviews(
    version_id: str,
    connection: Any = Depends(get_db_connection),
) -> list[dict[str, Any]]:
    try:
        _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        return [_review_response(review) for review in repositories.get_version_reviews(connection, version_id)]
    finally:
        _close_connection(connection)


@router.post(
    "/versions/{version_id}/supervisor-reviews",
    response_model=SupervisorReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_version_supervisor_review(
    version_id: str,
    payload: SupervisorReviewRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        if not payload.supervisor_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="supervisor_id is required.")
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
        supervisor_profile = _require_record(
            repositories.get_supervisor_profile(connection, payload.supervisor_id),
            "Supervisor not found.",
        )
        if not repositories.supervisor_is_assigned_to_student(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            student_id=proposal["student_id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor is not assigned to this proposal's student.",
            )
        if not repositories.get_version_analyses(connection, version_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analyze this proposal version before recording a supervisor decision.",
            )

        review = repositories.save_current_supervisor_review(
            connection,
            proposal_id=proposal["proposal_id"],
            version_id=version_id,
            supervisor_id=supervisor_profile["supervisor_id"],
            decision=_storage_decision(payload.decision),
            overall_comment=payload.comments.strip() if payload.comments else None,
        )
        enriched = repositories.get_latest_supervisor_review(
            connection,
            version_id=version_id,
            supervisor_id=supervisor_profile["supervisor_id"],
        )
        return _review_response(enriched or review)
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.post(
    "/versions/{version_id}/my-supervisor-review",
    response_model=SupervisorReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_my_version_supervisor_review(
    version_id: str,
    payload: SupervisorReviewRequest,
    supervisor_profile: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
        if not repositories.supervisor_is_assigned_to_student(
            connection,
            supervisor_id=supervisor_profile["supervisor_id"],
            student_id=proposal["student_id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor is not assigned to this proposal's student.",
            )
        if not repositories.get_version_analyses(connection, version_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Analyze this proposal version before recording a supervisor decision.",
            )

        review = repositories.save_current_supervisor_review(
            connection,
            proposal_id=proposal["proposal_id"],
            version_id=version_id,
            supervisor_id=supervisor_profile["supervisor_id"],
            decision=_storage_decision(payload.decision),
            overall_comment=payload.comments.strip() if payload.comments else None,
        )
        enriched = repositories.get_latest_supervisor_review(
            connection,
            version_id=version_id,
            supervisor_id=supervisor_profile["supervisor_id"],
        )
        return _review_response(enriched or review)
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.post("/versions/{version_id}/analyses/link", status_code=status.HTTP_201_CREATED)
def link_existing_analysis_to_version(
    version_id: str,
    payload: LinkVersionAnalysisRequest,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        analysis_id = payload.analysis_id.strip()
        if not analysis_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="analysis_id is required.")

        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
        analysis_record = core_logic.find_analysis_record_by_id(analysis_id)
        if analysis_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Completed Analyzer analysis was not found.",
            )

        existing_link = repositories.get_analysis(connection, analysis_id)
        if existing_link:
            if existing_link["version_id"] != version_id or existing_link["proposal_id"] != proposal["proposal_id"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This analysis_id is already linked to a different proposal version.",
                )
            return existing_link

        return repositories.create_analysis(
            connection,
            analysis_id=analysis_id,
            proposal_id=proposal["proposal_id"],
            version_id=version_id,
            request_id=analysis_record.get("request_id") or analysis_id,
            source=analysis_record.get("source") or version.get("source_type"),
            input_text_snapshot=analysis_record.get("input_text"),
        )
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)


@router.post("/versions/{version_id}/analyze", response_model=VersionAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def analyze_proposal_version(
    version_id: str,
    request: Request,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        version = _require_record(repositories.get_proposal_version(connection, version_id), "Version not found.")
        text = core_logic.clean_text(_version_text(version))
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        lock_key = f"{version_id}:{content_hash}"
        
        if lock_key not in _analysis_locks:
            _analysis_locks[lock_key] = asyncio.Lock()
            
        async with _analysis_locks[lock_key]:
            # Check cache to return immediately
            if lock_key in _analysis_cache:
                logger.info(f"Returning cached analysis for {lock_key}")
                return _analysis_cache[lock_key]
                
            proposal = _require_record(repositories.get_proposal(connection, version["proposal_id"]), "Proposal not found.")
            student = repositories.get_student(connection, proposal["student_id"])
            analysis_id = str(uuid4())
            
            import time
            start_time = time.time()
            # Run the ML pipeline in a threadpool
            pipeline = await run_in_threadpool(
                _run_version_analysis_pipeline,
                request=request,
                version=version,
                proposal=proposal,
                student=student,
                analysis_id=analysis_id,
            )
            logger.info(f"[TIMER] Full version analysis pipeline completed in {time.time() - start_time:.3f} seconds.")
            
            repositories.create_analysis(
                connection,
                analysis_id=analysis_id,
                proposal_id=proposal["proposal_id"],
                version_id=version_id,
                request_id=analysis_id,
                source=version.get("source_type"),
                input_text_snapshot=pipeline["text"],
            )
            
            result = {
                "analysis_id": analysis_id,
                "request_id": analysis_id,
                "proposal_id": proposal["proposal_id"],
                "version_id": version_id,
                "version_number": version["version_number"],
                "analysis": pipeline["analysis"],
                "semantic_grade": pipeline["semantic_grade"],
                "knowledge_graph": pipeline["knowledge_graph"],
                "knowledge_graph_error": pipeline["knowledge_graph_error"],
            }
            # Cache the exact dictionary for identical requests
            _analysis_cache[lock_key] = result
            return result
    except IntegrityError as exc:
        raise _constraint_error(exc) from exc
    finally:
        _close_connection(connection)
