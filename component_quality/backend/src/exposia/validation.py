"""Data validation and rule enforcement."""

import pandas as pd
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def validate_datasets(
    master_df: pd.DataFrame, 
    annotations_df: pd.DataFrame, 
    comments_df: pd.DataFrame
) -> List[Dict[str, Any]]:
    """Run validation rules and return a list of failed join / validation records."""
    issues = []
    
    if master_df.empty or annotations_df.empty or comments_df.empty:
        return issues
        
    # Rule 1: Every annotation ID should be unique within its source scope
    # (Checking global uniqueness for simplicity, as IDs seem globally unique)
    dup_anns = annotations_df[annotations_df.duplicated("annotation_id", keep=False)]
    if not dup_anns.empty:
        for _, row in dup_anns.iterrows():
            issues.append({
                "type": "duplicate_annotation_id",
                "id": row["annotation_id"],
                "author": row.get("author")
            })
            
    # Rule 2: comments.annotationId should reference an annotation when not null
    valid_ann_ids = set(annotations_df["annotation_id"].dropna())
    orphaned_comments = comments_df[
        (comments_df["annotation_id"].notna()) & 
        (comments_df["annotation_id"] != "") &
        (~comments_df["annotation_id"].isin(valid_ann_ids))
    ]
    if not orphaned_comments.empty:
        for _, row in orphaned_comments.iterrows():
            issues.append({
                "type": "orphaned_comment",
                "comment_id": row["comment_id"],
                "annotation_id_reference": row["annotation_id"]
            })
            
    # Rule 5: annotation tag must be one of Weakness, Strength, Highlight, Other
    valid_tags = {"Weakness", "Strength", "Highlight", "Other", "", None}
    invalid_tags = annotations_df[~annotations_df["annotation_tag"].isin(valid_tags)]
    if not invalid_tags.empty:
        for _, row in invalid_tags.iterrows():
            issues.append({
                "type": "invalid_annotation_tag",
                "id": row["annotation_id"],
                "tag": row["annotation_tag"]
            })
            
    # Rule 6: reviewer role must be one of student, assistant, expert
    valid_roles = {"student", "assistant", "expert", "", None}
    invalid_roles = annotations_df[~annotations_df["reviewer_role"].isin(valid_roles)]
    if not invalid_roles.empty:
        for _, row in invalid_roles.iterrows():
            issues.append({
                "type": "invalid_reviewer_role",
                "id": row["annotation_id"],
                "role": row["reviewer_role"]
            })

    return issues
