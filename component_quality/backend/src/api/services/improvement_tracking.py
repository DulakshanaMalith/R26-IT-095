"""Proposal-scoped version improvement summaries built from saved outputs only."""

from __future__ import annotations

from typing import Any

from src.api.services import core_logic
from src.db import history_repositories, repositories


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


def _semantic_percentage(grading_record: dict[str, Any] | None) -> float | None:
    if not isinstance(grading_record, dict):
        return None
    return _to_number(grading_record.get("semantic_percentage") or grading_record.get("percentage_score"))


def _latest_analysis_link(connection: Any, version_id: str) -> dict[str, Any] | None:
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
    connection: Any,
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
    reviews = repositories.get_version_reviews(connection, version["version_id"])
    latest_review = reviews[-1] if reviews else None

    return {
        "proposal_id": proposal_id,
        "version_id": version["version_id"],
        "version_number": version["version_number"],
        "version_label": _version_label(version),
        "original_filename": version.get("original_filename"),
        "analysis_id": analysis_id,
        "analysis_created_at": latest_link.get("created_at") if latest_link else None,
        "analyzed": latest_link is not None,
        "analysis_history_available": analysis_record is not None if latest_link else False,
        "grading_history_available": grading_record is not None if latest_link else False,
        "predicted_tag": analysis_record.get("predicted_tag") if isinstance(analysis_record, dict) else None,
        "semantic_percentage": _semantic_percentage(grading_record),
        "completeness_percentage": _completion_percentage(grading_record),
        "final_readiness_percentage": _readiness_percentage(grading_record),
        "final_status": _final_status(grading_record),
        "missing_sections": _missing_sections(grading_record),
        "section_scores": section_scores if isinstance(section_scores, dict) else {},
        "supervisor_decision": latest_review.get("decision") if latest_review else None,
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


def _version_label(snapshot: dict[str, Any]) -> str:
    return f"V{snapshot.get('version_number') or '?'}"


def _decision_rank(decision: Any) -> int:
    normalized = str(decision or "").strip().lower()
    if normalized in {"approved", "accepted", "ready_for_panel"}:
        return 0
    if normalized in {"completed", "complete", "reviewed"}:
        return 1
    if normalized in {"revision_requested", "request_revision"}:
        return 2
    return 3


def _decision_reason(decision: Any) -> str | None:
    normalized = str(decision or "").strip().lower()
    if normalized in {"approved", "accepted", "ready_for_panel"}:
        return "Supervisor decision is approved or ready for panel"
    if normalized in {"completed", "complete", "reviewed"}:
        return "Supervisor review is completed"
    if normalized in {"revision_requested", "request_revision"}:
        return "Supervisor revision is still requested"
    return "No supervisor decision has been recorded"


def _comparison_by_target(comparisons: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        comparison["to_version_id"]: comparison
        for comparison in comparisons
        if comparison.get("to_version_id")
    }


def _selection_metric_availability(eligible: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> dict[str, bool]:
    by_target = _comparison_by_target(comparisons)
    return {
        "missing_sections": all(snapshot.get("grading_history_available") for snapshot in eligible),
        "newly_missing_sections": all(by_target.get(snapshot["version_id"]) is not None for snapshot in eligible),
        "still_missing_sections": all(by_target.get(snapshot["version_id"]) is not None for snapshot in eligible),
        "resolved_missing_sections": all(by_target.get(snapshot["version_id"]) is not None for snapshot in eligible),
        "final_readiness_percentage": all(snapshot.get("final_readiness_percentage") is not None for snapshot in eligible),
        "completeness_percentage": all(snapshot.get("completeness_percentage") is not None for snapshot in eligible),
        "semantic_percentage": all(snapshot.get("semantic_percentage") is not None for snapshot in eligible),
    }


def _selection_counts(snapshot: dict[str, Any], by_target: dict[str, dict[str, Any]]) -> dict[str, int | None]:
    comparison = by_target.get(snapshot["version_id"])
    if comparison is None:
        return {
            "newly_missing_sections": None,
            "still_missing_sections": None,
            "resolved_missing_sections": None,
        }
    return {
        "newly_missing_sections": len(comparison.get("newly_missing_sections") or []),
        "still_missing_sections": len(comparison.get("still_missing_sections") or []),
        "resolved_missing_sections": len(comparison.get("resolved_missing_sections") or []),
    }


def _best_sort_key(
    snapshot: dict[str, Any],
    *,
    available: dict[str, bool],
    by_target: dict[str, dict[str, Any]],
) -> tuple[Any, ...]:
    counts = _selection_counts(snapshot, by_target)
    key: list[Any] = [_decision_rank(snapshot.get("supervisor_decision"))]
    if available["missing_sections"]:
        key.append(len(snapshot.get("missing_sections") or []))
    if available["newly_missing_sections"]:
        key.append(counts["newly_missing_sections"] if counts["newly_missing_sections"] is not None else 0)
    if available["still_missing_sections"]:
        key.append(counts["still_missing_sections"] if counts["still_missing_sections"] is not None else 0)
    if available["resolved_missing_sections"]:
        resolved = counts["resolved_missing_sections"] if counts["resolved_missing_sections"] is not None else 0
        key.append(-resolved)
    if available["final_readiness_percentage"]:
        key.append(-float(snapshot["final_readiness_percentage"]))
    if available["completeness_percentage"]:
        key.append(-float(snapshot["completeness_percentage"]))
    if available["semantic_percentage"]:
        key.append(-float(snapshot["semantic_percentage"]))
    key.append(-int(snapshot.get("version_number") or 0))
    return tuple(key)


def _join_sections(sections: list[str]) -> str:
    if not sections:
        return ""
    if len(sections) == 1:
        return sections[0]
    return f"{', '.join(sections[:-1])} and {sections[-1]}"


def _selection_reasons(
    selected: dict[str, Any],
    *,
    available: dict[str, bool],
    by_target: dict[str, dict[str, Any]],
    used_partial_evidence: bool,
) -> list[str]:
    reasons: list[str] = []
    missing = selected.get("missing_sections") or []
    if selected.get("grading_history_available"):
        reasons.append("No missing sections" if not missing else f"Fewer missing sections: {_join_sections(missing)}")
    comparison = by_target.get(selected["version_id"])
    resolved = comparison.get("resolved_missing_sections") if comparison else []
    newly_missing = comparison.get("newly_missing_sections") if comparison else []
    if resolved:
        reasons.append(f"Resolved {_join_sections(resolved)}")
    elif comparison is not None:
        reasons.append("No resolved sections recorded since the previous version")
    if comparison is None or not newly_missing:
        reasons.append("No structural regressions")
    else:
        reasons.append(f"Structural regressions are lower than competing versions")
    decision_reason = _decision_reason(selected.get("supervisor_decision"))
    if decision_reason:
        reasons.append(decision_reason)
    if used_partial_evidence:
        reasons.append("Selection used partial evidence because some grading or comparison metrics are unavailable")
    return reasons


def _confidence(eligible: list[dict[str, Any]], available: dict[str, bool]) -> str:
    if len(eligible) <= 1:
        return "medium"
    core_metrics = ["missing_sections", "newly_missing_sections", "still_missing_sections", "resolved_missing_sections"]
    return "high" if all(available.get(metric) for metric in core_metrics) else "medium"


def _regressions_after_best(
    selected: dict[str, Any],
    snapshots: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> list[dict[str, str]]:
    selected_number = int(selected.get("version_number") or 0)
    comparison_by_to = _comparison_by_target(comparisons)
    regressions: list[dict[str, str]] = []
    for snapshot in snapshots:
        if int(snapshot.get("version_number") or 0) <= selected_number:
            continue
        comparison = comparison_by_to.get(snapshot["version_id"])
        for section in (comparison.get("newly_missing_sections") or []) if comparison else []:
            regressions.append({
                "section": section,
                "message": f"{section} became missing in {_version_label(snapshot)}",
            })
    return regressions


def select_best_available_version(
    snapshots: list[dict[str, Any]],
    comparisons: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Select the best analyzed proposal version using saved deterministic evidence."""
    snapshot_copies = [dict(snapshot) for snapshot in snapshots if isinstance(snapshot, dict)]
    proposal_ids = {snapshot.get("proposal_id") for snapshot in snapshot_copies if snapshot.get("proposal_id")}
    if len(proposal_ids) > 1:
        raise ValueError("Cannot select a best version across different proposals.")

    eligible = [
        snapshot
        for snapshot in snapshot_copies
        if snapshot.get("analyzed") and (snapshot.get("analysis_history_available") or snapshot.get("grading_history_available"))
    ]
    if not eligible:
        return None

    comparison_copies = [dict(comparison) for comparison in comparisons or [] if isinstance(comparison, dict)]
    by_target = _comparison_by_target(comparison_copies)
    available = _selection_metric_availability(eligible, comparison_copies)
    comparable_grade_metrics = all(
        available[metric]
        for metric in ("final_readiness_percentage", "completeness_percentage", "semantic_percentage")
    )
    used_partial_evidence = not all(available.values())
    selected = sorted(
        eligible,
        key=lambda snapshot: _best_sort_key(snapshot, available=available, by_target=by_target),
    )[0]
    return {
        "version_id": selected["version_id"],
        "version_number": selected.get("version_number"),
        "version_label": _version_label(selected),
        "selection_type": "best_available",
        "basis": "structural_supervisor_and_grading_evidence" if comparable_grade_metrics else "structural_and_supervisor_evidence",
        "reasons": _selection_reasons(
            selected,
            available=available,
            by_target=by_target,
            used_partial_evidence=used_partial_evidence,
        ),
        "missing_sections": list(selected.get("missing_sections") or []),
        "newly_missing_sections": list((by_target.get(selected["version_id"]) or {}).get("newly_missing_sections") or []),
        "supervisor_decision": selected.get("supervisor_decision"),
        "confidence": _confidence(eligible, available),
        "used_partial_evidence": used_partial_evidence,
        "metrics_used": [name for name, is_available in available.items() if is_available],
        "eligible_version_count": len(eligible),
    }


def build_proposal_improvement(connection: Any, proposal_id: str) -> dict[str, Any] | None:
    proposal = repositories.get_proposal(connection, proposal_id)
    if proposal is None:
        return None

    versions = repositories.get_proposal_versions(connection, proposal_id)
    analysis_index = _history_by_analysis_id(history_repositories.list_analysis_history())
    grading_index = _history_by_analysis_id(history_repositories.list_grading_history())
    snapshots = [
        _version_snapshot(connection, proposal_id, version, analysis_index, grading_index)
        for version in versions
    ]
    comparisons = [
        _compare_snapshots(snapshots[index], snapshots[index + 1])
        for index in range(len(snapshots) - 1)
    ]
    best_version = select_best_available_version(snapshots, comparisons)
    latest_version = snapshots[-1] if snapshots else None
    latest_version_summary = {
        "version_id": latest_version["version_id"],
        "version_label": _version_label(latest_version),
    } if latest_version else None
    latest_is_best = bool(best_version and latest_version and best_version["version_id"] == latest_version["version_id"])
    selected_snapshot = next(
        (snapshot for snapshot in snapshots if best_version and snapshot["version_id"] == best_version["version_id"]),
        None,
    )

    return {
        "proposal_id": proposal["proposal_id"],
        "proposal_title": proposal["title"],
        "versions": snapshots,
        "comparisons": comparisons,
        "best_version": best_version,
        "latest_version": latest_version_summary,
        "latest_is_best": latest_is_best,
        "regressions_after_best": _regressions_after_best(selected_snapshot, snapshots, comparisons) if selected_snapshot else [],
        "latest_analysis_selection_rule": "latest analyses.created_at per version, with analysis_id as a stable tie-breaker",
    }
