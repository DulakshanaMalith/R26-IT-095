from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.post("/predict-weakness", response_model=WeaknessResponse)
def predict_weakness(payload: TextRequest, request: Request) -> WeaknessResponse:
    """Predict the annotation tag for academic text."""
    cleaned_text = clean_text(payload.text)
    validate_research_proposal_text(cleaned_text)
    text = prepare_model_text(cleaned_text)
    return WeaknessResponse(predicted_tag=predict_tag(request, text))

@router.post("/generate-feedback", response_model=FeedbackResponse)
def generate_feedback(payload: TextRequest) -> FeedbackResponse:
    """Retrieve feedback from semantically similar annotation examples."""
    cleaned_text = clean_text(payload.text)
    validate_research_proposal_text(cleaned_text)
    text = prepare_model_text(cleaned_text)
    return FeedbackResponse(feedback=retrieve_feedback(text, top_k=3))

@router.post("/grade-report", response_model=GradeReportResponse)
def grade_report(payload: GradeReportRequest) -> GradeReportResponse:
    """Generate a baseline semantic grading estimate for full report text."""
    print("[MODEL DEBUG] Endpoint /grade-report called")
    text = clean_text(payload.text)
    validate_research_proposal_text(text, payload.analysis_id)
    prepared_text = prepare_model_text(text, max_chars=50000)
    word_count = len(prepared_text.split())

    raw_predicted_score = grade_report_text(prepared_text)
    predicted_score = round(max(0.0, min(float(GRADING_MAX_SCORE), raw_predicted_score)), 2)
    percentage_score = percentage_from_score(predicted_score)
    label = score_label(percentage_score)
    section_scores = calculate_section_scores(prepared_text)
    assessment = build_final_proposal_assessment(
        text,
        predicted_score,
        percentage_score,
        label,
    )
    warning = GRADING_WARNING if word_count >= 300 else f"{GRADING_WARNING} {SHORT_GRADING_WARNING}"
    record = save_grading_record(
        analysis_id=payload.analysis_id,
        source=payload.source,
        filename=payload.filename,
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
    return GradeReportResponse(
        grading_id=record["id"],
        analysis_id=record.get("analysis_id"),
        predicted_score=predicted_score,
        max_score=GRADING_MAX_SCORE,
        percentage_score=percentage_score,
        semantic_percentage=percentage_score,
        semantic_label=label,
        score_label=label,
        section_scores=section_scores,
        proposal_completeness=record.get("proposal_completeness"),
        completeness_percentage=record.get("completeness_percentage"),
        missing_sections=record.get("missing_sections", []),
        submission_readiness=record.get("submission_readiness"),
        submission_status=record.get("submission_status"),
        submission_reason=record.get("submission_reason"),
        final_proposal_assessment=record.get("final_proposal_assessment"),
        final_readiness=record.get("final_readiness"),
        final_readiness_percentage=record.get("final_readiness_percentage"),
        final_readiness_label=record.get("final_readiness_label"),
        model_status=record["model_status"],
        warning=record["warning"],
    )

@router.post("/generate-report")
def generate_report(payload: GenerateReportRequest) -> Response:
    """Generate a downloadable PDF feedback report from real analysis data."""
    resolved_payload = normalize_report_semantic_label(resolve_report_payload_from_history(payload))
    input_text = resolved_payload.input_text.strip() or "No proposal text was provided."
    predicted_tag = resolved_payload.predicted_tag.strip() or "Not available"

    report_payload = resolved_payload.model_copy(
        update={"input_text": input_text, "predicted_tag": predicted_tag}
    )
    try:
        filename, pdf_bytes = generate_feedback_pdf(report_payload)
    except Exception as exc:
        logger.exception("Could not generate PDF report.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate PDF report: {exc}",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.post("/analyze", response_model=AnalysisResponse)
def analyze(payload: AnalyzeRequest, request: Request) -> AnalysisResponse:
    """Run weakness prediction, feedback retrieval, and recommendations."""
    print("[MODEL DEBUG] Endpoint /analyze called")
    existing_record = find_analysis_record_by_request_id(payload.request_id)
    if not existing_record:
        existing_record = find_analysis_record_by_id(payload.analysis_id)
    if existing_record:
        effective_record = effective_analysis_record(existing_record)
        print(f"Analysis history reused for analysis/request ID: {payload.analysis_id or payload.request_id}")
        return AnalysisResponse(
            analysis_id=record_analysis_id(effective_record) or effective_record["id"],
            request_id=effective_record.get("request_id"),
            input_text=effective_record.get("input_text", ""),
            predicted_tag=effective_record.get("predicted_tag", "Not available"),
            model_predicted_tag=effective_record.get("model_predicted_tag"),
            classification_reason=effective_record.get("classification_reason"),
            retrieved_feedback=effective_record.get("retrieved_feedback", []),
            recommended_resources=effective_record.get("recommended_resources", []),
            student_name=effective_record.get("student_name"),
            student_id=effective_record.get("student_id"),
            proposal_title=effective_record.get("proposal_title"),
        )
    text = clean_text(payload.text)
    validation = validate_research_proposal_text(text, payload.analysis_id)
    model_text = prepare_model_text(text)
    print("[MODEL DEBUG] Input text length:", len(model_text))
    model_predicted_tag = predict_tag(request, model_text)
    predicted_tag, classification_reason = analysis_tag_from_validation(model_predicted_tag, validation)
    feedback_matches = retrieve_feedback(model_text, top_k=3)
    feedback_context = " ".join(
        str(match.get("comment_text", "")) for match in feedback_matches
    )
    resources = get_recommended_resources(model_text, feedback_context, missing_sections=validation.missing_sections, top_k=3)
    record = save_analysis_record(
        analysis_id=payload.analysis_id,
        request_id=payload.request_id,
        text=text,
        predicted_tag=predicted_tag,
        model_predicted_tag=model_predicted_tag,
        classification_reason=classification_reason,
        feedback_matches=feedback_matches,
        resources=resources,
        source=payload.source,
        filename=payload.filename,
        student_name=payload.student_name,
        student_id=payload.student_id,
        proposal_title=payload.proposal_title,
    )

    return AnalysisResponse(
        analysis_id=record_analysis_id(record) or record["id"],
        request_id=record.get("request_id"),
        input_text=text,
        predicted_tag=predicted_tag,
        model_predicted_tag=model_predicted_tag,
        classification_reason=classification_reason,
        retrieved_feedback=feedback_matches,
        recommended_resources=resources,
        student_name=record["student_name"],
        student_id=record["student_id"],
        proposal_title=record["proposal_title"],
    )