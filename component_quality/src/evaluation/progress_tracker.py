import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock


PROGRESS_FILE = Path("data/progress/student_progress.json")
_LOCK = RLock()
SIGNIFICANT_SCORE_DELTA = 0.05


def _parse_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_progress_data(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        records = data.get("records")
        if isinstance(records, list):
            return records

        students = data.get("students")
        if isinstance(students, dict):
            flattened = []
            for student_id, student_records in students.items():
                if not isinstance(student_records, list):
                    continue
                for record in student_records:
                    if isinstance(record, dict):
                        flattened.append({"student_id": student_id, **record})
            return flattened

    return []


def load_progress():
    with _LOCK:
        if not PROGRESS_FILE.exists():
            return []

        try:
            with PROGRESS_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return []

        return _normalize_progress_data(data)


def save_progress(records):
    normalized_records = [record for record in records if isinstance(record, dict)]
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        with PROGRESS_FILE.open("w", encoding="utf-8") as handle:
            json.dump(normalized_records, handle, indent=2)


def reset_student_progress(student_id):
    normalized_student_id = str(student_id or "").strip()
    if not normalized_student_id:
        return {
            "student_id": normalized_student_id,
            "deleted_count": 0,
            "message": "No progress history available for this student.",
        }

    with _LOCK:
        records = load_progress()
        remaining_records = [
            record
            for record in records
            if str(record.get("student_id")).strip() != normalized_student_id
        ]
        deleted_count = len(records) - len(remaining_records)

        if deleted_count:
            save_progress(remaining_records)

    if deleted_count:
        message = "Progress history reset for this student."
    else:
        message = "No progress history available for this student."

    return {
        "student_id": normalized_student_id,
        "deleted_count": deleted_count,
        "message": message,
    }


def _normalize_version(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"version 1", "v1", "1"}:
        return "Version 1"
    if normalized in {"version 2", "v2", "2"}:
        return "Version 2"
    return str(value or "Version 1").strip() or "Version 1"


def _latest_record_for_version(records, version):
    version_records = [
        record
        for record in records
        if isinstance(record, dict) and _normalize_version(record.get("version")) == version
    ]
    if not version_records:
        return None

    return max(
        version_records,
        key=lambda record: (
            _parse_timestamp(record.get("timestamp"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )


def calculate_improvement(records, current_version=None):
    ordered_records = sorted(
        [record for record in records if isinstance(record, dict)],
        key=lambda record: (_parse_timestamp(record.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)),
    )

    if not ordered_records:
        return {
            "previous_score": None,
            "latest_score": None,
            "improvement": 0,
            "improvement_percentage": 0,
            "has_comparison": False,
            "comparison_status": "missing_submissions",
            "message": "No previous submission found.",
        }

    latest_record = ordered_records[-1]
    latest_score = round(_to_float(latest_record.get("final_score"), 0.0), 2)
    latest_version = _normalize_version(current_version or latest_record.get("version"))
    version_1_record = _latest_record_for_version(ordered_records, "Version 1")
    version_2_record = _latest_record_for_version(ordered_records, "Version 2")

    if latest_version == "Version 1":
        version_1_score = (
            round(_to_float(version_1_record.get("final_score"), 0.0), 2)
            if version_1_record
            else latest_score
        )
        return {
            "previous_score": version_1_score,
            "latest_score": None,
            "improvement": 0,
            "improvement_percentage": 0,
            "has_comparison": False,
            "comparison_status": "baseline_saved",
            "previous_version": "Version 1",
            "latest_version": None,
            "message": "Version 1 saved. Upload Version 2 to compare progress.",
        }

    if version_1_record is None:
        return {
            "previous_score": None,
            "latest_score": latest_score,
            "improvement": 0,
            "improvement_percentage": 0,
            "has_comparison": False,
            "comparison_status": "missing_version_1",
            "latest_version": latest_version,
            "message": "Upload Version 1 first to compare progress.",
        }

    version_1_score = round(_to_float(version_1_record.get("final_score"), 0.0), 2)

    if version_2_record is None:
        return {
            "previous_score": version_1_score,
            "latest_score": version_1_score,
            "improvement": 0,
            "improvement_percentage": 0,
            "has_comparison": False,
            "comparison_status": "missing_version_2",
            "latest_version": latest_version,
            "message": "Upload Version 2 to view progress comparison.",
        }

    version_2_score = round(_to_float(version_2_record.get("final_score"), 0.0), 2)
    improvement = round(version_2_score - version_1_score, 2)
    if abs(improvement) < SIGNIFICANT_SCORE_DELTA:
        improvement = 0.0

    if version_1_score:
        improvement_percentage = round(((version_2_score - version_1_score) / version_1_score) * 100, 2)
        if abs(improvement_percentage) < 0.1:
            improvement_percentage = 0.0
    else:
        improvement_percentage = 0.0

    if improvement > 0:
        message = (
            f"Version 2 improved by {improvement:.2f} points "
            f"({improvement_percentage:.2f}%) compared to Version 1."
        )
    elif improvement < 0:
        message = (
            f"Version 2 decreased by {abs(improvement):.2f} points "
            f"({abs(improvement_percentage):.2f}%) compared to Version 1."
        )
    else:
        message = "No significant change between Version 1 and Version 2."

    return {
        "previous_score": version_1_score,
        "latest_score": version_2_score,
        "improvement": improvement,
        "improvement_percentage": improvement_percentage,
        "has_comparison": True,
        "comparison_status": "ready",
        "previous_version": "Version 1",
        "latest_version": "Version 2",
        "message": message,
    }


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _detect_section_extremes(section_scores):
    if not isinstance(section_scores, list):
        return None, None

    normalized = []
    for row in section_scores:
        if not isinstance(row, dict):
            continue

        name = row.get("criterion") or row.get("name") or row.get("section")
        if not name:
            continue

        # Prefer weighted score for section ranking; fallback to raw score.
        value = row.get("weighted_score")
        if value is None:
            value = row.get("raw_score")
        if value is None:
            continue

        normalized.append((str(name), _to_float(value, 0.0)))

    if not normalized:
        return None, None

    strongest_section = max(normalized, key=lambda item: item[1])[0]
    weakest_section = min(normalized, key=lambda item: item[1])[0]
    return strongest_section, weakest_section


def _normalize_weaknesses(weaknesses):
    if not isinstance(weaknesses, list):
        return []

    normalized = []
    for item in weaknesses:
        if isinstance(item, str):
            value = item.strip()
            if value:
                normalized.append(value)
            continue

        if isinstance(item, dict):
            section = item.get("section") or item.get("criterion") or item.get("name")
            if section:
                normalized.append(str(section))

    return normalized


def update_student_progress(
    student_id,
    version,
    final_score,
    semantic_score=None,
    ml_score=None,
    grade=None,
    status=None,
    section_scores=None,
    weaknesses=None,
):
    normalized_student_id = str(student_id or "N/A").strip() or "N/A"
    normalized_version = _normalize_version(version)

    strongest_section, weakest_section = _detect_section_extremes(section_scores)
    normalized_weaknesses = _normalize_weaknesses(weaknesses)

    with _LOCK:
        records = load_progress()
        final_score_value = round(_to_float(final_score, 0.0), 2)

        record = {
            "student_id": normalized_student_id,
            "version": normalized_version,
            "final_score": final_score_value,
            "semantic_score": round(_to_float(semantic_score, 0.0), 2),
            "ml_score": round(_to_float(ml_score, 0.0), 2),
            "grade": str(grade or "N/A"),
            "status": str(status or "N/A"),
            "strongest_section": strongest_section,
            "weakest_section": weakest_section,
            "weaknesses": normalized_weaknesses,
            "improvement": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        records.append(record)
        student_records = [
            item
            for item in records
            if str(item.get("student_id")).strip() == normalized_student_id
        ]
        progress_result = calculate_improvement(student_records, current_version=normalized_version)
        record["improvement"] = progress_result.get("improvement", 0.0)
        record["improvement_percentage"] = progress_result.get("improvement_percentage", 0.0)
        save_progress(records)

    return progress_result
