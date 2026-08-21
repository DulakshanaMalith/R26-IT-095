"""Proposal-scoped version improvement summaries built from saved outputs only."""

from __future__ import annotations

import sqlite3
import json
from typing import Any

from src.api.services import core_logic
from src.db import repositories


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded_delta(new_value: float | None, old_value: float | None) -> float | None:
    if new_value is None or old_value is None:
        return None
    return round(new_value - old_value, 2)


def _normalize_sections(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized = []
    seen = set()
    for item in value:
        label = str(item or "").strip()
        if label and label not in seen:
            normalized.append(label)
            seen.add(label)
    return normalized


def _missing_sections(grading_record: dict[str, Any] | None) -> list[str]:
    if not isinstance(grading_record, dict):
        return []
    direct = _normalize_sections(grading_record.get("missing_sections"))
    if direct:
        return direct
    completeness = grading_record.get("proposal_completeness")
    if isinstance(completeness, dict):
        return _normalize_sections(completeness.get("missing_sections"))
    return []


def _completion_percentage(grading_record: dict[str, Any] | None) -> float | None:
    if not isinstance(grading_record, dict):
        return None
    direct = _to_number(grading_record.get("completeness_percentage"))
    if direct is not None:
        return direct
    completeness = grading_record.get("proposal_completeness")
    if isinstance(completeness, dict):
        return _to_number(completeness.get("percentage"))
    return None


def _readiness_percentage(grading_record: dict[str, Any] | None) -> float | None:
    if not isinstance(grading_record, dict):
        return None
    direct = _to_number(grading_record.get("final_readiness_percentage"))
    if direct is not None:
        return direct
    readiness = grading_record.get("final_readiness")
    if isinstance(readiness, dict):
        return _to_number(readiness.get("percentage"))
    return None


def _final_status(grading_record: dict[str, Any] | None) -> str | None:
    if not isinstance(grading_record, dict):
        return None
    status = grading_record.get("submission_status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    submission = grading_record.get("submission_readiness")
    if isinstance(submission, dict):
        nested = submission.get("status")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    label = grading_record.get("final_readiness_label")
    return label.strip() if isinstance(label, str) and label.strip() else None


def _latest_analysis_link(connection: sqlite3.Connection, version_id: str) -> dict[str, Any] | None:
    links = repositories.get_version_analyses(connection, version_id)
    if not links:
        return None
    return sorted(
        links,
        key=lambda item: (str(item.get("created_at") or ""), str(item.get("analysis_id") or "")),
    )[-1]


def _history_by_analysis_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        analysis_id = core_logic.record_analysis_id(record)
        if analysis_id:
            indexed[analysis_id] = record
    return indexed


def _load_json_history(path: Any) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _section_score_changes(old_scores: Any, new_scores: Any) -> list[dict[str, Any]]:
    if not isinstance(old_scores, dict) or not isinstance(new_scores, dict):
        return []
    changes = []
    for section in sorted(set(old_scores).intersection(new_scores)):
        old_value = _to_number(old_scores.get(section))
        new_value = _to_number(new_scores.get(section))
        delta = _rounded_delta(new_value, old_value)
        if delta is not None:
            changes.append(
                {
                    "section": section,
                    "from_score": old_value,
                    "to_score": new_value,
                    "delta": delta,
                }
            )
    return changes


def _version_snapshot(
    connection: sqlite3.Connection,
    proposal_id: str,
    version: dict[str, Any],
    analysis_history: dict[str, dict[str, Any]],
    grading_history: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    latest_link = _latest_analysis_link(connection, version["version_id"])
    analysis_id = latest_link.get("analysis_id") if latest_link else None
    analysis_record = analysis_history.get(analysis_id) if analysis_id else None
    grading_record = grading_history.get(analysis_id) if analysis_id else None
    section_scores = grading_record.get("section_scores") if isinstance(grading_record, dict) else None

    return {
        "proposal_id": proposal_id,
        "version_id": version["version_id"],
        "version_number": version["version_number"],
        "original_filename": version.get("original_filename"),
        "analysis_id": analysis_id,
        "analysis_created_at": latest_link.get("created_at") if latest_link else None,
        "analyzed": latest_link is not None,
        "analysis_history_available": analysis_record is not None if latest_link else False,
        "grading_history_available": grading_record is not None if latest_link else False,
        "predicted_tag": analysis_record.get("predicted_tag") if isinstance(analysis_record, dict) else None,
        "semantic_percentage": _to_number(grading_record.get("semantic_percentage") or grading_record.get("percentage_score"))
        if isinstance(grading_record, dict)
        else None,
        "completeness_percentage": _completion_percentage(grading_record),
        "final_readiness_percentage": _readiness_percentage(grading_record),
        "final_status": _final_status(grading_record),
        "missing_sections": _missing_sections(grading_record),
        "section_scores": section_scores if isinstance(section_scores, dict) else {},
    }


def _overall_direction(
    *,
    completeness_delta: float | None,
    readiness_delta: float | None,
    resolved_missing_sections: list[str],
    newly_missing_sections: list[str],
    section_score_changes: list[dict[str, Any]],
    sufficient_data: bool,
) -> str:
    if not sufficient_data:
        return "INSUFFICIENT_DATA"

    positive = False
    negative = False
    for delta in (completeness_delta, readiness_delta):
        if delta is None:
            continue
        positive = positive or delta > 0
        negative = negative or delta < 0
    positive = positive or bool(resolved_missing_sections)
    negative = negative or bool(newly_missing_sections)

    section_deltas = [change["delta"] for change in section_score_changes if change.get("delta") is not None]
    positive = positive or any(delta > 0 for delta in section_deltas)
    negative = negative or any(delta < 0 for delta in section_deltas)

    if positive and not negative:
        return "IMPROVED"
    if negative and not positive:
        return "REGRESSED"
    if positive and negative:
        return "MIXED"
    return "UNCHANGED"


def _compare_snapshots(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_missing = set(old.get("missing_sections") or [])
    new_missing = set(new.get("missing_sections") or [])
    resolved = sorted(old_missing - new_missing)
    newly_missing = sorted(new_missing - old_missing)
    still_missing = sorted(old_missing.intersection(new_missing))
    completeness_delta = _rounded_delta(new.get("completeness_percentage"), old.get("completeness_percentage"))
    readiness_delta = _rounded_delta(new.get("final_readiness_percentage"), old.get("final_readiness_percentage"))
    section_changes = _section_score_changes(old.get("section_scores"), new.get("section_scores"))
    sufficient_data = bool(old.get("grading_history_available") and new.get("grading_history_available"))

    return {
        "from_version": old["version_number"],
        "to_version": new["version_number"],
        "from_version_id": old["version_id"],
        "to_version_id": new["version_id"],
        "from_analysis_id": old.get("analysis_id"),
        "to_analysis_id": new.get("analysis_id"),
        "completeness_delta": completeness_delta,
        "readiness_delta": readiness_delta,
        "resolved_missing_sections": resolved,
        "newly_missing_sections": newly_missing,
        "still_missing_sections": still_missing,
        "section_score_changes": section_changes,
        "status_change": {
            "from_status": old.get("final_status"),
            "to_status": new.get("final_status"),
            "changed": old.get("final_status") != new.get("final_status"),
        },
        "tag_change": {
            "from_tag": old.get("predicted_tag"),
            "to_tag": new.get("predicted_tag"),
            "changed": old.get("predicted_tag") != new.get("predicted_tag"),
        },
        "overall_direction": _overall_direction(
            completeness_delta=completeness_delta,
            readiness_delta=readiness_delta,
            resolved_missing_sections=resolved,
            newly_missing_sections=newly_missing,
            section_score_changes=section_changes,
            sufficient_data=sufficient_data,
        ),
    }


def build_proposal_improvement(connection: sqlite3.Connection, proposal_id: str) -> dict[str, Any] | None:
    proposal = repositories.get_proposal(connection, proposal_id)
    if proposal is None:
        return None

    versions = repositories.get_proposal_versions(connection, proposal_id)
    analysis_index = _history_by_analysis_id(_load_json_history(core_logic.HISTORY_PATH))
    grading_index = _history_by_analysis_id(_load_json_history(core_logic.GRADING_HISTORY_PATH))
    snapshots = [
        _version_snapshot(connection, proposal_id, version, analysis_index, grading_index)
        for version in versions
    ]
    comparisons = [
        _compare_snapshots(snapshots[index], snapshots[index + 1])
        for index in range(len(snapshots) - 1)
    ]

    return {
        "proposal_id": proposal["proposal_id"],
        "proposal_title": proposal["title"],
        "versions": snapshots,
        "comparisons": comparisons,
        "latest_analysis_selection_rule": "latest SQLite analyses.created_at per version, with analysis_id as a stable tie-breaker",
    }
