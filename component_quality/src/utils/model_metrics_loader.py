from pathlib import Path
from typing import Any


METRICS_FILE_PATH = Path("models/scorers/model_metrics.txt")


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace("%", "").strip()
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _parse_metrics_text(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue

        key, value = line.split(":", 1)
        normalized_key = key.strip().lower()
        normalized_value = value.strip()

        if normalized_key == "model":
            parsed["model_type"] = normalized_value
        elif normalized_key == "pipeline":
            parsed["pipeline_label"] = normalized_value
        elif normalized_key == "dataset":
            parsed["dataset"] = normalized_value
        elif normalized_key == "mae":
            parsed["mae"] = _to_float(normalized_value)
        elif normalized_key == "rmse":
            parsed["rmse"] = _to_float(normalized_value)
        elif normalized_key in {"r2 score", "r2"}:
            parsed["r2_score"] = _to_float(normalized_value)
        elif normalized_key.startswith("consistency within +/-0.5"):
            parsed["consistency_0_5"] = _to_float(normalized_value)
        elif normalized_key.startswith("consistency within +/-1.0"):
            parsed["consistency_1_0"] = _to_float(normalized_value)

    # Keep compatibility with existing UI field while sourcing from latest metrics.
    parsed["approx_accuracy"] = parsed.get("consistency_1_0")
    return parsed


def load_latest_model_metrics() -> dict[str, Any]:
    if not METRICS_FILE_PATH.exists():
        return {}

    try:
        text = METRICS_FILE_PATH.read_text(encoding="utf-8")
    except OSError:
        return {}

    return _parse_metrics_text(text)
