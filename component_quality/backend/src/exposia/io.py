"""File I/O utilities for reading and writing dataset artifacts."""

import csv
import json
import logging
from pathlib import Path
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

def read_json(path: Path, default: Any = None) -> Any:
    """Read JSON from path, returning default when the file is absent or invalid."""
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid JSON in {path}: {exc}")
        return default
    except OSError as exc:
        logger.warning(f"Could not read {path}: {exc}")
        return default

def write_json(path: Path, data: Any) -> None:
    """Write data to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error(f"Failed to write JSON to {path}: {exc}")

def read_text_file(path: Path) -> str:
    """Read a text file with a small encoding fallback."""
    if not path.exists():
        return ""
        
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except OSError as exc:
        logger.warning(f"Could not read {path}: {exc}")
        return ""

def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    """Write a list of dictionaries to a CSV file."""
    if not rows:
        logger.warning(f"No rows to write to {path}")
        return
        
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract all possible fieldnames in case some rows are missing keys
    fieldnames = set()
    for row in rows:
        fieldnames.update(row.keys())
    
    # Sort them for deterministic output (but keep known identifiers first if present)
    ordered_fields = []
    priorities = ["author", "review_id", "annotation_id", "comment_id", "topic", "submission_type", "reviewer_role"]
    for p in priorities:
        if p in fieldnames:
            ordered_fields.append(p)
            fieldnames.remove(p)
            
    ordered_fields.extend(sorted(list(fieldnames)))

    try:
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=ordered_fields)
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        logger.error(f"Failed to write CSV to {path}: {exc}")

def json_for_csv(value: Any) -> str:
    """Serialize nested values for storage in one CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)
