import json
import os
import re


def load_json(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_text_file(content: str, path: str) -> None:
    """
    Save text content to a UTF-8 file.
    Creates parent directory automatically if missing.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def extract_student_id_from_text(text: str) -> str | None:
    """
    Attempt to locate a student ID in free text using expected patterns.

    Matches strings like 'IT22101624' (literal 'IT' + 8 digits).
    Returns the first match in uppercase or None when no match found.
    """
    if not text:
        return None

    # Normalize to simple ASCII and upper-case for matching
    try:
        hay = text.upper()
    except Exception:
        hay = str(text)

    m = re.search(r"\bIT\d{8}\b", hay)
    if m:
        return m.group(0)
    return None