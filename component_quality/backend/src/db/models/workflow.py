"""PostgreSQL models for supervisor-owned proposal/version workflows."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('supervisor', 'admin', 'panel')", name="ck_users_role"),
        CheckConstraint("is_active IN (0, 1)", name="ck_users_is_active"),
    )

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SupervisorProfile(Base):
    __tablename__ = "supervisor_profiles"

    supervisor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.user_id"), unique=True, nullable=False)
    department: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (CheckConstraint("active IN (0, 1)", name="ck_students_active"),)

    student_id: Mapped[str] = mapped_column(Text, primary_key=True)
    academic_student_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    program: Mapped[str | None] = mapped_column(Text)
    cohort: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SupervisorStudentAssignment(Base):
    __tablename__ = "supervisor_student_assignments"
    __table_args__ = (
        CheckConstraint(
            "assignment_role IN ('primary_supervisor', 'co_supervisor')",
            name="ck_supervisor_student_assignments_role",
        ),
        CheckConstraint("active IN (0, 1)", name="ck_supervisor_student_assignments_active"),
        Index(
            "uq_active_supervisor_student_role",
            "supervisor_id",
            "student_id",
            "assignment_role",
            unique=True,
            postgresql_where=text("active = 1"),
        ),
        Index(
            "uq_active_primary_supervisor_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("active = 1 AND assignment_role = 'primary_supervisor'"),
        ),
    )

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    supervisor_id: Mapped[str] = mapped_column(Text, ForeignKey("supervisor_profiles.supervisor_id"), nullable=False)
    student_id: Mapped[str] = mapped_column(Text, ForeignKey("students.student_id"), nullable=False)
    assignment_role: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_at: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Proposal(Base):
    __tablename__ = "proposals"

    proposal_id: Mapped[str] = mapped_column(Text, primary_key=True)
    student_id: Mapped[str] = mapped_column(Text, ForeignKey("students.student_id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class ProposalVersion(Base):
    __tablename__ = "proposal_versions"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version_number", name="uq_proposal_versions_proposal_version_number"),
        UniqueConstraint("version_id", "proposal_id", name="uq_proposal_versions_version_proposal"),
    )

    version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("proposals.proposal_id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(Text)
    original_file_path: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    edited_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    original_document_path: Mapped[str | None] = mapped_column(Text)
    original_document_name: Mapped[str | None] = mapped_column(Text)
    original_document_content_type: Mapped[str | None] = mapped_column(Text)
    original_document_size: Mapped[int | None] = mapped_column(Integer)
    original_document_sha256: Mapped[str | None] = mapped_column(Text)
    original_document_uploaded_at: Mapped[str | None] = mapped_column(Text)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_analyses_version_proposal",
        ),
    )

    analysis_id: Mapped[str] = mapped_column(Text, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("proposals.proposal_id"), nullable=False)
    version_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    input_text_snapshot: Mapped[str | None] = mapped_column(Text)


class SupervisorReview(Base):
    __tablename__ = "supervisor_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('SEND_FEEDBACK', 'REVISION_REQUESTED', 'READY_FOR_PANEL', 'REVIEWED')",
            name="ck_supervisor_reviews_decision",
        ),
        ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_supervisor_reviews_version_proposal",
        ),
    )

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("proposals.proposal_id"), nullable=False)
    version_id: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor_id: Mapped[str] = mapped_column(Text, ForeignKey("supervisor_profiles.supervisor_id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    overall_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class AiSupervisorReviewDraft(Base):
    __tablename__ = "ai_supervisor_review_drafts"
    __table_args__ = (
        UniqueConstraint("version_id", "analysis_id", name="uq_ai_supervisor_review_drafts_version_analysis"),
        ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_ai_supervisor_review_drafts_version_proposal",
        ),
    )

    draft_id: Mapped[str] = mapped_column(Text, primary_key=True)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("proposals.proposal_id"), nullable=False)
    version_id: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_id: Mapped[str] = mapped_column(Text, ForeignKey("analyses.analysis_id"), nullable=False)
    draft_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str | None] = mapped_column(Text)
    llm_metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class SupervisorReviewDraft(Base):
    __tablename__ = "supervisor_review_drafts"
    __table_args__ = (
        UniqueConstraint("supervisor_id", "version_id", "analysis_id", name="uq_supervisor_review_drafts_supervisor_version_analysis"),
    )

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    version_id: Mapped[str] = mapped_column(Text, ForeignKey("proposal_versions.version_id"), nullable=False)
    analysis_id: Mapped[str] = mapped_column(Text, ForeignKey("analyses.analysis_id"), nullable=False)
    supervisor_id: Mapped[str] = mapped_column(Text, ForeignKey("supervisor_profiles.supervisor_id"), nullable=False)
    ai_draft_id: Mapped[str] = mapped_column(Text, ForeignKey("ai_supervisor_review_drafts.draft_id"), nullable=False)
    overall_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    strengths_json: Mapped[str] = mapped_column(Text, nullable=False)
    areas_requiring_improvement_json: Mapped[str] = mapped_column(Text, nullable=False)
    methodology_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_validation_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations_json: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_revision_instructions_json: Mapped[str] = mapped_column(Text, nullable=False)
    supervisor_comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('FEEDBACK_SENT', 'REVISION_REQUESTED', 'READY_FOR_PANEL')",
            name="ck_notification_logs_type",
        ),
    )

    notification_id: Mapped[str] = mapped_column(Text, primary_key=True)
    student_id: Mapped[str] = mapped_column(Text, ForeignKey("students.student_id"), nullable=False)
    proposal_id: Mapped[str] = mapped_column(Text, ForeignKey("proposals.proposal_id"), nullable=False)
    version_id: Mapped[str | None] = mapped_column(Text, ForeignKey("proposal_versions.version_id"))
    analysis_id: Mapped[str | None] = mapped_column(Text, ForeignKey("analyses.analysis_id"))
    supervisor_id: Mapped[str | None] = mapped_column(Text, ForeignKey("supervisor_profiles.supervisor_id"))
    supervisor_review_draft_id: Mapped[str | None] = mapped_column(Text, ForeignKey("supervisor_review_drafts.review_id"))
    review_id: Mapped[str | None] = mapped_column(Text, ForeignKey("supervisor_reviews.review_id"))
    recipient_email: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_name: Mapped[str | None] = mapped_column(Text)
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    report_reference: Mapped[str | None] = mapped_column(Text)
