import json
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
REVIEW_CRITERIA_PATH = ROOT_DIR / "dataset" / "supplementary" / "review_criteria.json"
EXPOSE_CRITERIA_PATH = ROOT_DIR / "dataset" / "supplementary" / "expose_criteria.json"

def load_criteria_as_text() -> str:
    """
    Loads official Exposía criteria and formats them for the LLM prompt.
    """
    if not REVIEW_CRITERIA_PATH.exists():
        return ""

    try:
        with open(REVIEW_CRITERIA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""

    rubrics = data.get("rubrics", [])
    if not rubrics:
        return ""

    block = "### OFFICIAL EVALUATION CRITERIA\n"
    block += "Use the following rubrics to guide your evaluation. Ensure any flagged issues map to these standards.\n\n"

    for rubric in rubrics:
        block += f"Rubric: {rubric.get('name', 'Unknown')}\n"
        block += f"Description: {rubric.get('description', '')}\n"
        
        criteria = rubric.get("criteria", [])
        if criteria:
            for crit in criteria:
                block += f"  - Criterion: {crit.get('name', '')}\n"
                block += f"    Definition: {crit.get('description', '')}\n"
        block += "\n"

    return block
