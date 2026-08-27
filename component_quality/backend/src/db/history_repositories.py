"""Repositories for PostgreSQL-backed analysis, grading, and graph histories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from src.db.models.history import AnalysisHistoryRecord, GradingRecord, KnowledgeGraphRecord
from src.db.session import get_session_factory


def _timestamp(record: dict[str, Any]) -> str:
    value = record.get("timestamp")
    return value if isinstance(value, str) and value.strip() else datetime.now(timezone.utc).isoformat()


def _record_id(record: dict[str, Any]) -> str:
    value = record.get("id")
    return value if isinstance(value, str) and value.strip() else str(uuid4())


def _analysis_id(record: dict[str, Any]) -> str | None:
    value = record.get("analysis_id") or record.get("id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _payload(row: Any) -> dict[str, Any]:
    payload = dict(row.payload or {})
    return payload


def list_analysis_history() -> list[dict[str, Any]]:
    with get_session_factory()() as session:
        rows = session.scalars(select(AnalysisHistoryRecord).order_by(AnalysisHistoryRecord.timestamp, AnalysisHistoryRecord.id)).all()
        return [_payload(row) for row in rows]


def replace_analysis_history(records: list[dict[str, Any]]) -> None:
    with get_session_factory()() as session:
        session.execute(delete(AnalysisHistoryRecord))
        for record in records:
            if isinstance(record, dict):
                session.merge(_analysis_model(record))
        session.commit()


def append_analysis_record(record: dict[str, Any]) -> dict[str, Any]:
    with get_session_factory()() as session:
        session.merge(_analysis_model(record))
        session.commit()
    return record


def delete_analysis_history_record(analysis_id: str) -> dict[str, Any] | None:
    with get_session_factory()() as session:
        row = session.scalars(
            select(AnalysisHistoryRecord)
            .where(
                (AnalysisHistoryRecord.analysis_id == analysis_id)
                | (AnalysisHistoryRecord.id == analysis_id)
            )
            .order_by(AnalysisHistoryRecord.timestamp.desc(), AnalysisHistoryRecord.id.desc())
        ).first()
        if row is None:
            return None
        payload = _payload(row)
        session.delete(row)
        session.commit()
        return payload


def _analysis_model(record: dict[str, Any]) -> AnalysisHistoryRecord:
    rid = _record_id(record)
    analysis_id = _analysis_id(record) or rid
    payload = dict(record)
    payload["id"] = rid
    payload["analysis_id"] = analysis_id
    payload["timestamp"] = _timestamp(payload)
    return AnalysisHistoryRecord(
        id=rid,
        analysis_id=analysis_id,
        request_id=payload.get("request_id"),
        timestamp=payload["timestamp"],
        source=payload.get("source"),
        filename=payload.get("filename"),
        student_name=payload.get("student_name"),
        student_id=payload.get("student_id"),
        proposal_title=payload.get("proposal_title"),
        input_text=payload.get("input_text"),
        input_preview=payload.get("input_preview"),
        predicted_tag=payload.get("predicted_tag"),
        model_predicted_tag=payload.get("model_predicted_tag"),
        classification_reason=payload.get("classification_reason"),
        retrieved_feedback=payload.get("retrieved_feedback"),
        recommended_resources=payload.get("recommended_resources"),
        payload=payload,
    )


def list_grading_history() -> list[dict[str, Any]]:
    with get_session_factory()() as session:
        rows = session.scalars(select(GradingRecord).order_by(GradingRecord.timestamp, GradingRecord.id)).all()
        return [_payload(row) for row in rows]


def replace_grading_history(records: list[dict[str, Any]]) -> None:
    with get_session_factory()() as session:
        session.execute(delete(GradingRecord))
        for record in records:
            if isinstance(record, dict):
                session.merge(_grading_model(record))
        session.commit()


def append_grading_record(record: dict[str, Any]) -> dict[str, Any]:
    with get_session_factory()() as session:
        session.merge(_grading_model(record))
        session.commit()
    return record


def _float_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _grading_model(record: dict[str, Any]) -> GradingRecord:
    rid = _record_id(record)
    payload = dict(record)
    payload["id"] = rid
    payload["timestamp"] = _timestamp(payload)
    return GradingRecord(
        id=rid,
        analysis_id=_analysis_id(payload),
        timestamp=payload["timestamp"],
        source=payload.get("source"),
        filename=payload.get("filename"),
        input_text=payload.get("input_text"),
        input_preview=payload.get("input_preview"),
        word_count=_int_value(payload.get("word_count")),
        predicted_score=_float_value(payload.get("predicted_score")),
        max_score=_int_value(payload.get("max_score")),
        percentage_score=_float_value(payload.get("percentage_score")),
        semantic_percentage=_float_value(payload.get("semantic_percentage")),
        completeness_percentage=_float_value(payload.get("completeness_percentage")),
        final_readiness_percentage=_float_value(payload.get("final_readiness_percentage")),
        score_label=payload.get("score_label"),
        semantic_label=payload.get("semantic_label"),
        final_readiness_label=payload.get("final_readiness_label"),
        model_status=payload.get("model_status"),
        warning=payload.get("warning"),
        section_scores=payload.get("section_scores"),
        proposal_completeness=payload.get("proposal_completeness"),
        submission_readiness=payload.get("submission_readiness"),
        final_proposal_assessment=payload.get("final_proposal_assessment"),
        final_readiness=payload.get("final_readiness"),
        missing_sections=payload.get("missing_sections"),
        payload=payload,
    )


def list_graph_history() -> list[dict[str, Any]]:
    with get_session_factory()() as session:
        rows = session.scalars(select(KnowledgeGraphRecord).order_by(KnowledgeGraphRecord.timestamp, KnowledgeGraphRecord.id)).all()
        return [_payload(row) for row in rows]


def replace_graph_history(records: list[dict[str, Any]]) -> None:
    with get_session_factory()() as session:
        session.execute(delete(KnowledgeGraphRecord))
        for index, record in enumerate(records):
            if isinstance(record, dict):
                session.merge(_graph_model(record, index=index))
        session.commit()


def append_graph_record(record: dict[str, Any]) -> dict[str, Any]:
    with get_session_factory()() as session:
        session.add(_graph_model(record))
        session.commit()
    return record


def _graph_model(record: dict[str, Any], *, index: int | None = None) -> KnowledgeGraphRecord:
    rid = record.get("id")
    if not isinstance(rid, str) or not rid.strip():
        source = _analysis_id(record) or record.get("timestamp") or str(uuid4())
        suffix = str(index) if index is not None else str(uuid4())
        rid = f"kg-{source}-{suffix}"
    payload = dict(record)
    payload["id"] = rid
    payload["timestamp"] = _timestamp(payload)
    return KnowledgeGraphRecord(
        id=rid,
        analysis_id=_analysis_id(payload),
        timestamp=payload["timestamp"],
        filename=payload.get("filename"),
        concept_count=_int_value(payload.get("concept_count")),
        concepts=payload.get("concepts"),
        edges=payload.get("edges") or payload.get("relationships"),
        missing_concepts=payload.get("missing_concepts"),
        implicit_concepts=payload.get("implicit_concepts"),
        payload=payload,
    )
