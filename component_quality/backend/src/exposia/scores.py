"""Score parsing and criteria normalization."""

from typing import List, Dict, Any

def flatten_scores(scores_list: List[Dict[str, Any]], review_hash: str = "") -> List[Dict[str, Any]]:
    """Flatten a list of score records into criterion-level rows."""
    flattened = []
    for record in scores_list:
        author = record.get("author", "")
        submission_type = record.get("type", "")
        grader = record.get("grader", "")
        role = record.get("role", "")
        group = record.get("group", "")
        criteria = record.get("criteria", {})
        
        for criterion_name, score_val in criteria.items():
            flattened.append({
                "author": author,
                "submission_type": submission_type,
                "grader": grader,
                "role": role,
                "group": group,
                "review_hash": review_hash,
                "criterion": criterion_name,
                "score": score_val
            })
            
    return flattened

def extract_criteria_hierarchy(expose_criteria_data: dict, review_criteria_data: dict) -> List[Dict[str, Any]]:
    """Extract a normalized table of criteria definitions from the supplementary JSON files."""
    rows = []
    
    for c_type, data in [("expose", expose_criteria_data), ("review", review_criteria_data)]:
        if not data:
            continue
            
        rubrics = data.get("rubrics", [])
        for rubric in rubrics:
            rubric_name = rubric.get("name", "")
            
            for criterion in rubric.get("criteria", []):
                rows.append({
                    "criteria_type": c_type,
                    "rubric": rubric_name,
                    "criterion": criterion.get("name", ""),
                    "code": criterion.get("code", ""),
                    "description": criterion.get("description", ""),
                    "max_points": criterion.get("maxPoints", ""),
                    "min_points": criterion.get("minPoints", "")
                })
                
    return rows
