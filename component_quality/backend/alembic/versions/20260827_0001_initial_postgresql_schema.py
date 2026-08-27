"""initial PostgreSQL schema

Revision ID: 20260827_0001
Revises:
Create Date: 2026-08-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260827_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text()),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("role IN ('supervisor', 'admin', 'panel')", name="ck_users_role"),
        sa.CheckConstraint("is_active IN (0, 1)", name="ck_users_is_active"),
    )
    op.create_table(
        "students",
        sa.Column("student_id", sa.Text(), primary_key=True),
        sa.Column("academic_student_id", sa.Text(), nullable=False, unique=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("program", sa.Text()),
        sa.Column("cohort", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("active IN (0, 1)", name="ck_students_active"),
    )
    op.create_table(
        "supervisor_profiles",
        sa.Column("supervisor_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id"), nullable=False, unique=True),
        sa.Column("department", sa.Text()),
        sa.Column("title", sa.Text()),
    )
    op.create_table(
        "supervisor_student_assignments",
        sa.Column("assignment_id", sa.Text(), primary_key=True),
        sa.Column("supervisor_id", sa.Text(), sa.ForeignKey("supervisor_profiles.supervisor_id"), nullable=False),
        sa.Column("student_id", sa.Text(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("assignment_role", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.Text(), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "assignment_role IN ('primary_supervisor', 'co_supervisor')",
            name="ck_supervisor_student_assignments_role",
        ),
        sa.CheckConstraint("active IN (0, 1)", name="ck_supervisor_student_assignments_active"),
    )
    op.create_index(
        "uq_active_supervisor_student_role",
        "supervisor_student_assignments",
        ["supervisor_id", "student_id", "assignment_role"],
        unique=True,
        postgresql_where=sa.text("active = 1"),
    )
    op.create_index(
        "uq_active_primary_supervisor_per_student",
        "supervisor_student_assignments",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("active = 1 AND assignment_role = 'primary_supervisor'"),
    )
    op.create_table(
        "proposals",
        sa.Column("proposal_id", sa.Text(), primary_key=True),
        sa.Column("student_id", sa.Text(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_version_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "proposal_versions",
        sa.Column("version_id", sa.Text(), primary_key=True),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("proposals.proposal_id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.Text()),
        sa.Column("source_type", sa.Text()),
        sa.Column("original_file_path", sa.Text()),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("edited_text", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("original_document_path", sa.Text()),
        sa.Column("original_document_name", sa.Text()),
        sa.Column("original_document_content_type", sa.Text()),
        sa.Column("original_document_size", sa.Integer()),
        sa.Column("original_document_sha256", sa.Text()),
        sa.Column("original_document_uploaded_at", sa.Text()),
        sa.UniqueConstraint("proposal_id", "version_number", name="uq_proposal_versions_proposal_version_number"),
        sa.UniqueConstraint("version_id", "proposal_id", name="uq_proposal_versions_version_proposal"),
    )
    op.create_table(
        "analyses",
        sa.Column("analysis_id", sa.Text(), primary_key=True),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("proposals.proposal_id"), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("input_text_snapshot", sa.Text()),
        sa.ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_analyses_version_proposal",
        ),
    )
    op.create_table(
        "supervisor_reviews",
        sa.Column("review_id", sa.Text(), primary_key=True),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("proposals.proposal_id"), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("supervisor_id", sa.Text(), sa.ForeignKey("supervisor_profiles.supervisor_id"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("overall_comment", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('SEND_FEEDBACK', 'REVISION_REQUESTED', 'READY_FOR_PANEL', 'REVIEWED')",
            name="ck_supervisor_reviews_decision",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_supervisor_reviews_version_proposal",
        ),
    )
    op.create_table(
        "ai_supervisor_review_drafts",
        sa.Column("draft_id", sa.Text(), primary_key=True),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("proposals.proposal_id"), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("analysis_id", sa.Text(), sa.ForeignKey("analyses.analysis_id"), nullable=False),
        sa.Column("draft_json", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("llm_metadata_json", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("version_id", "analysis_id", name="uq_ai_supervisor_review_drafts_version_analysis"),
        sa.ForeignKeyConstraint(
            ["version_id", "proposal_id"],
            ["proposal_versions.version_id", "proposal_versions.proposal_id"],
            name="fk_ai_supervisor_review_drafts_version_proposal",
        ),
    )
    op.create_table(
        "supervisor_review_drafts",
        sa.Column("review_id", sa.Text(), primary_key=True),
        sa.Column("version_id", sa.Text(), sa.ForeignKey("proposal_versions.version_id"), nullable=False),
        sa.Column("analysis_id", sa.Text(), sa.ForeignKey("analyses.analysis_id"), nullable=False),
        sa.Column("supervisor_id", sa.Text(), sa.ForeignKey("supervisor_profiles.supervisor_id"), nullable=False),
        sa.Column("ai_draft_id", sa.Text(), sa.ForeignKey("ai_supervisor_review_drafts.draft_id"), nullable=False),
        sa.Column("overall_assessment", sa.Text(), nullable=False),
        sa.Column("strengths_json", sa.Text(), nullable=False),
        sa.Column("areas_requiring_improvement_json", sa.Text(), nullable=False),
        sa.Column("methodology_feedback", sa.Text(), nullable=False),
        sa.Column("evaluation_validation_feedback", sa.Text(), nullable=False),
        sa.Column("recommendations_json", sa.Text(), nullable=False),
        sa.Column("suggested_revision_instructions_json", sa.Text(), nullable=False),
        sa.Column("supervisor_comments", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("supervisor_id", "version_id", "analysis_id", name="uq_supervisor_review_drafts_supervisor_version_analysis"),
    )
    op.create_table(
        "notification_logs",
        sa.Column("notification_id", sa.Text(), primary_key=True),
        sa.Column("student_id", sa.Text(), sa.ForeignKey("students.student_id"), nullable=False),
        sa.Column("proposal_id", sa.Text(), sa.ForeignKey("proposals.proposal_id"), nullable=False),
        sa.Column("version_id", sa.Text(), sa.ForeignKey("proposal_versions.version_id")),
        sa.Column("analysis_id", sa.Text(), sa.ForeignKey("analyses.analysis_id")),
        sa.Column("supervisor_id", sa.Text(), sa.ForeignKey("supervisor_profiles.supervisor_id")),
        sa.Column("supervisor_review_draft_id", sa.Text(), sa.ForeignKey("supervisor_review_drafts.review_id")),
        sa.Column("review_id", sa.Text(), sa.ForeignKey("supervisor_reviews.review_id")),
        sa.Column("recipient_email", sa.Text()),
        sa.Column("subject", sa.Text()),
        sa.Column("notification_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_name", sa.Text()),
        sa.Column("provider_message_id", sa.Text()),
        sa.Column("report_reference", sa.Text()),
        sa.CheckConstraint(
            "notification_type IN ('FEEDBACK_SENT', 'REVISION_REQUESTED', 'READY_FOR_PANEL')",
            name="ck_notification_logs_type",
        ),
    )
    op.create_table(
        "analysis_history_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("analysis_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text()),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("filename", sa.Text()),
        sa.Column("student_name", sa.Text()),
        sa.Column("student_id", sa.Text()),
        sa.Column("proposal_title", sa.Text()),
        sa.Column("input_text", sa.Text()),
        sa.Column("input_preview", sa.Text()),
        sa.Column("predicted_tag", sa.Text()),
        sa.Column("model_predicted_tag", sa.Text()),
        sa.Column("classification_reason", sa.Text()),
        sa.Column("retrieved_feedback", postgresql.JSONB()),
        sa.Column("recommended_resources", postgresql.JSONB()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_analysis_history_records_analysis_id", "analysis_history_records", ["analysis_id"])
    op.create_index("ix_analysis_history_records_request_id", "analysis_history_records", ["request_id"])
    op.create_index("ix_analysis_history_records_timestamp", "analysis_history_records", ["timestamp"])
    op.create_table(
        "grading_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("analysis_id", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("filename", sa.Text()),
        sa.Column("input_text", sa.Text()),
        sa.Column("input_preview", sa.Text()),
        sa.Column("word_count", sa.Integer()),
        sa.Column("predicted_score", sa.Float()),
        sa.Column("max_score", sa.Integer()),
        sa.Column("percentage_score", sa.Float()),
        sa.Column("semantic_percentage", sa.Float()),
        sa.Column("completeness_percentage", sa.Float()),
        sa.Column("final_readiness_percentage", sa.Float()),
        sa.Column("score_label", sa.Text()),
        sa.Column("semantic_label", sa.Text()),
        sa.Column("final_readiness_label", sa.Text()),
        sa.Column("model_status", sa.Text()),
        sa.Column("warning", sa.Text()),
        sa.Column("section_scores", postgresql.JSONB()),
        sa.Column("proposal_completeness", postgresql.JSONB()),
        sa.Column("submission_readiness", postgresql.JSONB()),
        sa.Column("final_proposal_assessment", postgresql.JSONB()),
        sa.Column("final_readiness", postgresql.JSONB()),
        sa.Column("missing_sections", postgresql.JSONB()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_grading_records_analysis_id", "grading_records", ["analysis_id"])
    op.create_index("ix_grading_records_timestamp", "grading_records", ["timestamp"])
    op.create_table(
        "knowledge_graph_records",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("analysis_id", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text()),
        sa.Column("concept_count", sa.Integer()),
        sa.Column("concepts", postgresql.JSONB()),
        sa.Column("edges", postgresql.JSONB()),
        sa.Column("missing_concepts", postgresql.JSONB()),
        sa.Column("implicit_concepts", postgresql.JSONB()),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_knowledge_graph_records_analysis_id", "knowledge_graph_records", ["analysis_id"])
    op.create_index("ix_knowledge_graph_records_timestamp", "knowledge_graph_records", ["timestamp"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_knowledge_graph_records_timestamp", "knowledge_graph_records"),
        ("ix_knowledge_graph_records_analysis_id", "knowledge_graph_records"),
        ("ix_grading_records_timestamp", "grading_records"),
        ("ix_grading_records_analysis_id", "grading_records"),
        ("ix_analysis_history_records_timestamp", "analysis_history_records"),
        ("ix_analysis_history_records_request_id", "analysis_history_records"),
        ("ix_analysis_history_records_analysis_id", "analysis_history_records"),
        ("uq_active_primary_supervisor_per_student", "supervisor_student_assignments"),
        ("uq_active_supervisor_student_role", "supervisor_student_assignments"),
    ):
        op.drop_index(index_name, table_name=table_name)
    for table_name in (
        "knowledge_graph_records",
        "grading_records",
        "analysis_history_records",
        "notification_logs",
        "supervisor_review_drafts",
        "ai_supervisor_review_drafts",
        "supervisor_reviews",
        "analyses",
        "proposal_versions",
        "proposals",
        "supervisor_student_assignments",
        "supervisor_profiles",
        "students",
        "users",
    ):
        op.drop_table(table_name)
