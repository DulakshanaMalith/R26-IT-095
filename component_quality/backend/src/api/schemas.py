from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Any
from src.reviewer.schemas import ReviewResult

class TextRequest(BaseModel):
    """Request body containing academic text to analyze."""

    text: str = Field(min_length=1, description="Academic text to analyze")

class ReviewRequest(BaseModel):
    """Request body for LLM autonomous review."""
    proposal_text: str = Field(min_length=1)
    mode: str = Field(default="llm_only", description="Review mode: llm_only, llm_rag, or llm_rag_criteria")
    top_k: int = Field(default=5)
    excluded_author_ids: list[str] | None = None

class ReviewEndpointResponse(BaseModel):
    review: ReviewResult
    metadata: dict

class AnalyzeRequest(TextRequest):
    """Request body for the complete analysis pipeline."""

    analysis_id: str | None = Field(default=None, description="Client-generated ID shared across one analysis flow")
    request_id: str | None = Field(default=None, description="Optional idempotency key for one user analysis action")
    source: str | None = Field(default=None, description="Optional input source: text or pdf")
    filename: str | None = Field(default=None, description="Optional uploaded filename")
    student_name: str | None = Field(default=None, description="Optional student name")
    student_id: str | None = Field(default=None, description="Optional student identifier")
    proposal_title: str | None = Field(default=None, description="Optional proposal title")
    learning_needs: list[dict[str, Any]] = Field(default_factory=list, description="Optional explicit structural or length deficiencies to target resources for")


class ResourceRequest(TextRequest):
    """Request body for resource recommendation."""

    feedback: str = Field(default="", description="Optional retrieved feedback")
    analysis_id: str | None = Field(default=None, description="Optional linked analysis record ID")
    learning_needs: list[dict[str, Any]] = Field(default_factory=list, description="Optional explicit structural or length deficiencies to target resources for")


class KnowledgeGraphRequest(TextRequest):
    """Request body for concept mapping."""

    filename: str | None = Field(default=None, description="Optional source filename")
    analysis_id: str | None = Field(default=None, description="Optional linked analysis record ID")


class GradeReportRequest(BaseModel):
    """Request body for semantic report grading."""

    text: str = Field(description="Full proposal or report text to grade")
    source: str | None = Field(default=None, description="Optional input source: text or pdf")
    filename: str | None = Field(default=None, description="Optional uploaded filename")
    analysis_id: str | None = Field(default=None, description="Optional linked analysis record ID")


class SemanticGradePayload(BaseModel):
    """Optional semantic grade payload included in downloadable reports."""

    predicted_score: float | None = None
    max_score: int | None = None
    percentage_score: float | None = None
    score_label: str | None = None
    section_scores: dict[str, Any] = Field(default_factory=dict)
    model_status: str | None = None
    warning: str | None = None


class FinalReadinessPayload(BaseModel):
    """Hybrid readiness score combining semantic quality and proposal completeness."""

    percentage: float | None = None
    label: str | None = None
    semantic_percentage: float | None = None
    completeness_percentage: float | None = None
    explanation: str | None = None


class ProposalCompletenessPayload(BaseModel):
    """Academic proposal completeness assessment derived from document validation."""

    percentage: float | None = None
    detected_sections: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    deductions: dict[str, int] = Field(default_factory=dict)
    sections_evidence: dict[str, Any] = Field(default_factory=dict)
    validation_confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    status: str | None = None



class SubmissionReadinessPayload(BaseModel):
    """Supervisor-facing final proposal readiness assessment."""

    status: str | None = None
    reason: str | None = None
    recommendation: str | None = None


class FinalProposalAssessmentPayload(BaseModel):
    """Combined non-ML academic assessment layer."""

    semantic_grade: dict[str, Any] = Field(default_factory=dict)
    proposal_completeness: ProposalCompletenessPayload | None = None
    submission_readiness: SubmissionReadinessPayload | None = None
    final_readiness: FinalReadinessPayload | None = None


class KnowledgeGraphPayload(BaseModel):
    """Knowledge graph payload included in downloadable reports."""

    concepts: list[Any] = Field(default_factory=list)
    edges: list[Any] = Field(default_factory=list)
    missing_concepts: list[Any] = Field(default_factory=list)
    implicit_concepts: list[Any] = Field(default_factory=list)
    concept_evidence: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "missing_concepts" not in normalized and "missingConcepts" in normalized:
            normalized["missing_concepts"] = normalized["missingConcepts"]
        return normalized


class GenerateReportRequest(BaseModel):
    """Request body for generating a downloadable AI feedback report."""

    analysis_id: str | None = None
    filename: str | None = None
    source: str | None = None
    student_name: str | None = None
    student_id: str | None = None
    proposal_title: str | None = None
    analysis_timestamp: str | None = None
    input_text: str = ""
    predicted_tag: str = ""
    feedback: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_graph: KnowledgeGraphPayload = Field(default_factory=KnowledgeGraphPayload)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    semantic_grade: SemanticGradePayload | None = None
    proposal_completeness: ProposalCompletenessPayload | None = None
    submission_readiness: SubmissionReadinessPayload | None = None
    final_proposal_assessment: FinalProposalAssessmentPayload | None = None
    final_readiness: FinalReadinessPayload | None = None
    final_readiness_percentage: float | None = None
    final_readiness_label: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        legacy_map = {
            "studentName": "student_name",
            "studentId": "student_id",
            "studentID": "student_id",
            "proposalTitle": "proposal_title",
            "title": "proposal_title",
            "knowledgeGraph": "knowledge_graph",
            "semanticGrade": "semantic_grade",
            "analysisTimestamp": "analysis_timestamp",
        }
        for legacy_key, target_key in legacy_map.items():
            if target_key not in normalized and legacy_key in normalized:
                normalized[target_key] = normalized[legacy_key]
        return normalized


class WeaknessResponse(BaseModel):
    predicted_tag: str


class FeedbackResponse(BaseModel):
    feedback: list[dict[str, Any]]


class ResourceResponse(BaseModel):
    resources: list[dict[str, Any]]


class AnalysisResponse(BaseModel):
    analysis_id: str
    request_id: str | None = None
    input_text: str
    predicted_tag: str
    model_predicted_tag: str | None = None
    classification_reason: str | None = None
    retrieved_feedback: list[dict[str, Any]]
    recommended_resources: list[dict[str, Any]]
    student_name: str | None = None
    student_id: str | None = None
    proposal_title: str | None = None


class HistoryResponse(BaseModel):
    total: int
    items: list[dict[str, Any]]


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterSupervisorRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    confirm_password: str = Field(min_length=1)


class SupervisorIdentityResponse(BaseModel):
    user_id: str
    supervisor_id: str
    email: str
    name: str
    role: str
    department: str | None = None
    title: str | None = None


class CreateStudentRequest(BaseModel):
    academic_student_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    email: str | None = None
    program: str | None = None
    cohort: str | None = None


class UpdateStudentEmailRequest(BaseModel):
    email: str | None = None


class StudentResponse(BaseModel):
    student_id: str
    academic_student_id: str
    full_name: str
    email: str | None = None
    program: str | None = None
    cohort: str | None = None
    created_at: str
    updated_at: str
    active: int


class CreateAssignmentRequest(BaseModel):
    assignment_role: str = Field(default="primary_supervisor", pattern="^(primary_supervisor|co_supervisor)$")


class AssignmentResponse(BaseModel):
    assignment_id: str
    supervisor_id: str
    student_id: str
    assignment_role: str
    assigned_at: str
    active: int


class SupervisorStudentResponse(StudentResponse):
    assignment_id: str
    assignment_role: str
    assigned_at: str


class CreateProposalRequest(BaseModel):
    title: str = Field(min_length=1)


class ProposalResponse(BaseModel):
    proposal_id: str
    student_id: str
    title: str
    status: str
    current_version_id: str | None = None
    created_at: str
    updated_at: str


class CreateProposalVersionRequest(BaseModel):
    original_filename: str | None = None
    source_type: str | None = None
    extracted_text: str | None = None


class CreateRevisedProposalVersionRequest(CreateProposalVersionRequest):
    supervisor_id: str = Field(min_length=1)


class LinkVersionAnalysisRequest(BaseModel):
    analysis_id: str = Field(min_length=1)


class SupervisorReviewDraftRequest(BaseModel):
    analysis_id: str = Field(min_length=1)


class SupervisorReviewDraftContent(BaseModel):
    overall_assessment: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    areas_requiring_improvement: list[str] = Field(default_factory=list)
    methodology_feedback: str = Field(min_length=1)
    evaluation_validation_feedback: str = Field(min_length=1)
    recommendations: list[str] = Field(default_factory=list)
    suggested_revision_instructions: list[str] = Field(default_factory=list)


class SupervisorReviewDraftResponse(BaseModel):
    draft_id: str
    proposal_id: str
    version_id: str
    analysis_id: str
    draft: SupervisorReviewDraftContent
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    llm_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SaveSupervisorEditedReviewDraftRequest(SupervisorReviewDraftContent):
    analysis_id: str = Field(min_length=1)
    supervisor_id: str = Field(min_length=1)
    supervisor_comments: str | None = None


class SupervisorEditedReviewDraftResponse(BaseModel):
    review_id: str
    version_id: str
    analysis_id: str
    supervisor_id: str
    ai_draft_id: str
    draft: SupervisorReviewDraftContent
    supervisor_comments: str | None = None
    created_at: str
    updated_at: str


class SendFeedbackRequest(BaseModel):
    analysis_id: str = Field(min_length=1)
    supervisor_id: str = Field(min_length=1)


class FeedbackDeliveryResponse(BaseModel):
    notification_id: str | None = None
    version_id: str
    analysis_id: str
    supervisor_id: str
    student_id: str
    recipient_email: str | None = None
    subject: str | None = None
    status: str
    notification_type: str = "FEEDBACK_SENT"
    created_at: str | None = None
    sent_at: str | None = None
    error_message: str | None = None
    provider_name: str | None = None
    provider_message_id: str | None = None
    report_reference: str | None = None


class ReviewOutcomeRequest(BaseModel):
    analysis_id: str = Field(min_length=1)
    supervisor_id: str = Field(min_length=1)
    decision: str = Field(pattern="^(COMPLETE_REVIEW|REQUEST_REVISION)$")
    comments: str | None = None


class ReviewOutcomeResponse(BaseModel):
    review_id: str | None = None
    version_id: str
    analysis_id: str
    supervisor_id: str
    decision: str | None = None
    status: str
    label: str
    comments: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SupervisorReviewRequest(BaseModel):
    supervisor_id: str | None = Field(default=None, min_length=1)
    decision: str = Field(pattern="^(REQUEST_REVISION|READY_FOR_PANEL|REVIEWED|REVISION_REQUESTED)$")
    comments: str | None = None


class SupervisorReviewResponse(BaseModel):
    review_id: str
    proposal_id: str
    version_id: str
    supervisor_id: str
    supervisor_name: str | None = None
    decision: str
    comments: str | None = None
    created_at: str
    updated_at: str


class DashboardRecentProposalResponse(BaseModel):
    student_id: str
    student_name: str
    academic_student_id: str
    proposal_id: str
    proposal_title: str
    current_version_id: str | None = None
    current_version_number: int | None = None
    last_upload: str | None = None
    analysis_state: str
    supervisor_review_state: str


class SupervisorDashboardResponse(BaseModel):
    assigned_students: int
    with_proposals: int
    analyzed_current_versions: int
    waiting_for_analysis: int
    revision_requested: int
    reviewed: int
    recent_proposals: list[DashboardRecentProposalResponse]


class ProposalVersionResponse(BaseModel):
    version_id: str
    proposal_id: str
    version_number: int
    original_filename: str | None = None
    source_type: str | None = None
    original_file_path: str | None = None
    extracted_text: str | None = None
    edited_text: str | None = None
    created_at: str
    submitted_at: str | None = None
    status: str


class KnowledgeGraphResponse(BaseModel):
    analysis_id: str | None = None
    concepts: list[str]
    edges: list[dict[str, Any]]
    missing_concepts: list[str]
    implicit_concepts: list[str] = Field(default_factory=list)
    concept_evidence: dict[str, str] = Field(default_factory=dict)
    nlp_warning: str | None = None


class VersionAnalysisResponse(BaseModel):
    analysis_id: str
    request_id: str | None = None
    proposal_id: str
    version_id: str
    version_number: int
    analysis: AnalysisResponse
    semantic_grade: GradeReportResponse
    knowledge_graph: KnowledgeGraphResponse | None = None
    knowledge_graph_error: str | None = None


class GradeReportResponse(BaseModel):
    grading_id: str | None = None
    analysis_id: str | None = None
    predicted_score: float
    max_score: int
    percentage_score: float
    semantic_percentage: float | None = None
    semantic_label: str | None = None
    score_label: str
    section_scores: dict[str, int]
    proposal_completeness: ProposalCompletenessPayload | None = None
    missing_sections: list[str] = Field(default_factory=list)
    submission_readiness: SubmissionReadinessPayload | None = None
    submission_status: str | None = None
    submission_reason: str | None = None
    final_proposal_assessment: FinalProposalAssessmentPayload | None = None
    completeness_percentage: float | None = None
    final_readiness: FinalReadinessPayload | None = None
    final_readiness_percentage: float | None = None
    final_readiness_label: str | None = None
    model_status: str
    warning: str


class GenerateReportResponse(BaseModel):
    download_url: str
    filename: str


class SupervisorCommonResource(BaseModel):
    title: str
    category: str
    count: int


class SupervisorDailyCount(BaseModel):
    date: str
    count: int


class SupervisorRecentAnalysis(BaseModel):
    id: str | None = None
    timestamp: str | None = None
    source: str = "unknown"
    filename: str | None = None
    predicted_tag: str | None = None
    model_predicted_tag: str | None = None
    classification_reason: str | None = None
    input_preview: str = ""


class SupervisorAnalyticsResponse(BaseModel):
    total_analyses: int
    tag_distribution: dict[str, int]
    most_common_tag: str | None = None
    feedback_count_total: int
    resource_count_total: int
    common_resources: list[SupervisorCommonResource]
    daily_counts: list[SupervisorDailyCount]
    daily_review_count: list[SupervisorDailyCount]
    recent_analyses: list[SupervisorRecentAnalysis]
    warning: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "total_analyses": 2,
                "tag_distribution": {
                    "Weakness": 0,
                    "Strength": 2,
                    "Other": 0,
                    "Highlight": 0,
                },
                "most_common_tag": "Strength",
                "feedback_count_total": 6,
                "resource_count_total": 6,
                "common_resources": [
                    {
                        "title": "Designing a Reproducible Methodology",
                        "category": "Methodology",
                        "count": 2,
                    }
                ],
                "daily_counts": [{"date": "2026-07-02", "count": 2}],
                "recent_analyses": [
                    {
                        "id": "32cd74b9-c3b9-460a-b8b6-f74365a5a27c",
                        "timestamp": "2026-07-02T05:11:05.075215+00:00",
                        "source": "pdf",
                        "filename": "proposal.pdf",
                        "predicted_tag": "Strength",
                        "input_preview": "Project proposal preview...",
                    }
                ],
                "warning": None,
            }
        }


class ValidatedRetrievedFeedbackItem(BaseModel):
    is_supported: bool
    validated_feedback: str

class ValidatedRetrievedFeedbackList(BaseModel):
    items: list[ValidatedRetrievedFeedbackItem]

