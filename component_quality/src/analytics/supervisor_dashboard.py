import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.model_metrics_loader import load_latest_model_metrics


PROGRESS_FILE = Path("data/progress/student_progress.json")


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_timestamp(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _normalize_records(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        records = data.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]

        students = data.get("students")
        if isinstance(students, dict):
            flattened: list[dict] = []
            for student_id, student_records in students.items():
                if not isinstance(student_records, list):
                    continue
                for record in student_records:
                    if isinstance(record, dict):
                        flattened.append({"student_id": student_id, **record})
            return flattened

    return []


def load_supervisor_records() -> list[dict]:
    if not PROGRESS_FILE.exists():
        return []

    try:
        with PROGRESS_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []

    return _normalize_records(payload)


def _calculate_average_improvement(records: list[dict]) -> float:
    direct_improvements = [
        _to_float(record.get("improvement"), None)
        for record in records
        if isinstance(record, dict) and record.get("improvement") is not None
    ]
    direct_improvements = [value for value in direct_improvements if value is not None]

    if not direct_improvements:
        return 0.0
    return round(sum(direct_improvements) / len(direct_improvements), 2)


def _score_to_grade(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _extract_weakness_sections(record: dict) -> list[str]:
    sections: list[str] = []

    value = record.get("weaknesses")
    if not isinstance(value, list):
        return sections

    for item in value:
        if isinstance(item, str):
            normalized = item.strip()
            if normalized:
                sections.append(normalized)
            continue

        if isinstance(item, dict):
            section = item.get("section") or item.get("criterion") or item.get("name")
            if section:
                sections.append(str(section))
    return sections


def get_latest_records_by_student_and_version(records: list[dict], version_filter: str | None = None) -> list[dict]:
    """
    Filter records to only the latest submission per (student_id, version) combination.
    
    Args:
        records: List of evaluation records from student_progress.json
        version_filter: Optional filter for specific version (e.g., "Version 2"). 
                       If provided, only returns latest records for that version.
    
    Returns:
        List of latest records, one per (student_id, version) combination
    """
    # Group records by (student_id, version) tuple
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    
    for record in records:
        if not isinstance(record, dict):
            continue
        
        student_id = str(record.get("student_id") or "").strip()
        version = str(record.get("version") or "").strip()
        
        # Skip records with missing student_id or version
        if not student_id or not version:
            continue
        
        # Skip if version_filter is specified and doesn't match
        if version_filter and version != version_filter:
            continue
        
        grouped[(student_id, version)].append(record)
    
    # For each (student_id, version) group, keep only the latest record
    latest_records: list[dict] = []
    for (student_id, version), group in grouped.items():
        # Sort by timestamp (descending - newest first)
        sorted_group = sorted(
            group,
            key=lambda r: _parse_timestamp(r.get("timestamp")),
            reverse=True
        )
        # Keep the latest (first after sorting)
        if sorted_group:
            latest_records.append(sorted_group[0])
    
    return latest_records


def _extract_section_rows(record: dict) -> list[dict]:
    for key in ("section_scores", "section_evaluation"):
        value = record.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def build_supervisor_dashboard(version_filter: str | None = None) -> dict:
    """
    Build supervisor analytics dashboard using only the latest records per student+version.
    
    Args:
        version_filter: Optional filter for specific version (e.g., "Version 2").
                       If provided, only analytics for that version are included.
    
    Returns:
        Dictionary with aggregated analytics metrics
    """
    all_records = load_supervisor_records()
    
    # Filter to only latest records per (student_id, version) combination
    records = get_latest_records_by_student_and_version(all_records, version_filter=version_filter)

    if not records:
        empty_grade_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        return {
            "total_reports": 0,
            "unique_students": 0,
            "average_final_score": 0.0,
            "average_improvement": 0.0,
            "grade_distribution": empty_grade_distribution,
            "common_weaknesses": [],
            "most_common_weaknesses": [],
            "strongest_common_section": None,
            "weakest_common_section": None,
        }

    total_reports = len(records)
    unique_students = len(
        {
            str(record.get("student_id")).strip()
            for record in records
            if str(record.get("student_id") or "").strip()
        }
    )

    final_scores = [_to_float(record.get("final_score"), 0.0) for record in records]
    average_final_score = round(sum(final_scores) / len(final_scores), 2) if final_scores else 0.0

    grade_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for score in final_scores:
        grade_distribution[_score_to_grade(score)] += 1

    weakness_counter: Counter[str] = Counter()
    for record in records:
        weakness_counter.update(_extract_weakness_sections(record))

    common_weaknesses = [
        {"section": section, "count": count}
        for section, count in weakness_counter.most_common(5)
    ]

    section_totals: dict[str, list[float]] = defaultdict(list)
    strongest_counter: Counter[str] = Counter()
    weakest_counter: Counter[str] = Counter()
    for record in records:
        strongest_name = record.get("strongest_section")
        weakest_name = record.get("weakest_section")
        if strongest_name:
            strongest_counter.update([str(strongest_name)])
        if weakest_name:
            weakest_counter.update([str(weakest_name)])

        for section in _extract_section_rows(record):
            criterion = section.get("criterion") or section.get("name") or section.get("section")
            if not criterion:
                continue

            value = section.get("raw_score")
            if value is None:
                value = section.get("weighted_score")
            if value is None:
                similarity = section.get("similarity_score")
                if similarity is not None:
                    value = _to_float(similarity, 0.0) * 100

            if value is None:
                continue

            section_totals[str(criterion)].append(_to_float(value, 0.0))

    strongest_common_section = None
    weakest_common_section = None

    if strongest_counter:
        strongest_common_section = strongest_counter.most_common(1)[0][0]
    if weakest_counter:
        weakest_common_section = weakest_counter.most_common(1)[0][0]

    if (not strongest_common_section or not weakest_common_section) and section_totals:
        section_averages = {
            name: (sum(scores) / len(scores))
            for name, scores in section_totals.items()
            if scores
        }
        if section_averages:
            if not strongest_common_section:
                strongest_common_section = max(section_averages, key=section_averages.get)
            if not weakest_common_section:
                weakest_common_section = min(section_averages, key=section_averages.get)

    return {
        "total_reports": total_reports,
        "unique_students": unique_students,
        "average_final_score": average_final_score,
        "average_improvement": _calculate_average_improvement(records),
        "grade_distribution": grade_distribution,
        "common_weaknesses": common_weaknesses,
        "most_common_weaknesses": common_weaknesses,
        "strongest_common_section": strongest_common_section,
        "weakest_common_section": weakest_common_section,
        "model_metrics": load_latest_model_metrics(),
    }
