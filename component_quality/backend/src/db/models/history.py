"""PostgreSQL models for formerly JSON-backed runtime histories."""

from __future__ import annotations

from sqlalchemy import Float, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AnalysisHistoryRecord(Base):
    __tablename__ = "analysis_history_records"
    __table_args__ = (
        Index("ix_analysis_history_records_analysis_id", "analysis_id"),
        Index("ix_analysis_history_records_request_id", "request_id"),
        Index("ix_analysis_history_records_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    student_name: Mapped[str | None] = mapped_column(Text)
    student_id: Mapped[str | None] = mapped_column(Text)
    proposal_title: Mapped[str | None] = mapped_column(Text)
    input_text: Mapped[str | None] = mapped_column(Text)
    input_preview: Mapped[str | None] = mapped_column(Text)
    predicted_tag: Mapped[str | None] = mapped_column(Text)
    model_predicted_tag: Mapped[str | None] = mapped_column(Text)
    classification_reason: Mapped[str | None] = mapped_column(Text)
    retrieved_feedback: Mapped[list | None] = mapped_column(JSONB)
    recommended_resources: Mapped[list | None] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class GradingRecord(Base):
    __tablename__ = "grading_records"
    __table_args__ = (
        Index("ix_grading_records_analysis_id", "analysis_id"),
        Index("ix_grading_records_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    analysis_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    input_text: Mapped[str | None] = mapped_column(Text)
    input_preview: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int | None] = mapped_column(Integer)
    predicted_score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[int | None] = mapped_column(Integer)
    percentage_score: Mapped[float | None] = mapped_column(Float)
    semantic_percentage: Mapped[float | None] = mapped_column(Float)
    completeness_percentage: Mapped[float | None] = mapped_column(Float)
    final_readiness_percentage: Mapped[float | None] = mapped_column(Float)
    score_label: Mapped[str | None] = mapped_column(Text)
    semantic_label: Mapped[str | None] = mapped_column(Text)
    final_readiness_label: Mapped[str | None] = mapped_column(Text)
    model_status: Mapped[str | None] = mapped_column(Text)
    warning: Mapped[str | None] = mapped_column(Text)
    section_scores: Mapped[dict | None] = mapped_column(JSONB)
    proposal_completeness: Mapped[dict | None] = mapped_column(JSONB)
    submission_readiness: Mapped[dict | None] = mapped_column(JSONB)
    final_proposal_assessment: Mapped[dict | None] = mapped_column(JSONB)
    final_readiness: Mapped[dict | None] = mapped_column(JSONB)
    missing_sections: Mapped[list | None] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class KnowledgeGraphRecord(Base):
    __tablename__ = "knowledge_graph_records"
    __table_args__ = (
        Index("ix_knowledge_graph_records_analysis_id", "analysis_id"),
        Index("ix_knowledge_graph_records_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    analysis_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text)
    concept_count: Mapped[int | None] = mapped_column(Integer)
    concepts: Mapped[list | None] = mapped_column(JSONB)
    edges: Mapped[list | None] = mapped_column(JSONB)
    missing_concepts: Mapped[list | None] = mapped_column(JSONB)
    implicit_concepts: Mapped[list | None] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
