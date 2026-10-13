"""Reporting and auditing generation."""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import json

from .io import write_json

def generate_quality_report(
    master_df: pd.DataFrame,
    exposes_df: pd.DataFrame,
    reviews_df: pd.DataFrame,
    annotations_df: pd.DataFrame,
    comments_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    output_dir: Path
) -> Dict[str, Any]:
    """Generate the data quality statistics and write markdown/JSON reports."""
    
    stats = {}
    
    # Base Counts
    stats["number_of_authors"] = int(exposes_df["author"].nunique()) if not exposes_df.empty else 0
    stats["number_of_exposes"] = int(len(exposes_df)) if not exposes_df.empty else 0
    stats["number_of_drafts"] = int(exposes_df["draft_text"].notna().sum()) if not exposes_df.empty else 0
    stats["number_of_finals"] = int(exposes_df["final_text"].notna().sum()) if not exposes_df.empty else 0
    stats["number_of_reviews"] = int(len(reviews_df)) if not reviews_df.empty else 0
    stats["number_of_annotations"] = int(len(annotations_df)) if not annotations_df.empty else 0
    stats["number_of_comments"] = int(len(comments_df)) if not comments_df.empty else 0
    
    # Specifics
    if not comments_df.empty and not annotations_df.empty:
        ann_ids = set(annotations_df["annotation_id"].dropna())
        stats["number_of_side_comments"] = int(len(comments_df[~comments_df["annotation_id"].isin(ann_ids)]))
        
        com_ann_ids = set(comments_df["annotation_id"].dropna())
        stats["number_of_annotations_without_comments"] = int(len(annotations_df[~annotations_df["annotation_id"].isin(com_ann_ids)]))
        
        # We checked orphaned comments in validation, here we just check raw nulls/orphans
        stats["number_of_comments_without_annotations"] = stats["number_of_side_comments"]
    
    if not annotations_df.empty:
        stats["alignment_exact_position"] = int(len(annotations_df[annotations_df["alignment_status"] == "exact_position"]))
        stats["alignment_text_quote"] = int(len(annotations_df[annotations_df["alignment_status"] == "text_quote"]))
        stats["alignment_normalized_match"] = int(len(annotations_df[annotations_df["alignment_status"] == "normalized_match"]))
        stats["alignment_failed"] = int(len(annotations_df[annotations_df["alignment_status"] == "failed"]))
        
        def clean_dict(d):
            return {str(k): int(v) for k, v in d.items()}
            
        stats["label_distribution"] = clean_dict(annotations_df["annotation_tag"].value_counts(dropna=False).to_dict())
        stats["reviewer_role_distribution"] = clean_dict(annotations_df["reviewer_role"].value_counts(dropna=False).to_dict())
        stats["group_distribution"] = clean_dict(annotations_df["group"].value_counts(dropna=False).to_dict())
        
    if not scores_df.empty:
        stats["number_of_records_with_criterion_level_scores"] = int(len(scores_df))
        def clean_dict(d):
            return {str(k): int(v) for k, v in d.items()}
        stats["score_distribution_summary"] = clean_dict(scores_df["score"].value_counts(dropna=False).to_dict())
        
        # draft/final pairs
        draft_authors = set(scores_df[scores_df["submission_type"] == "draft"]["author"])
        final_authors = set(scores_df[scores_df["submission_type"] == "final"]["author"])
        stats["number_of_draft_final_pairs"] = int(len(draft_authors.intersection(final_authors)))
        
    # Write JSON
    write_json(output_dir / "data_quality_report.json", stats)
    write_json(output_dir / "build_summary.json", stats)
    
    # Write Markdown
    md_content = ["# Exposía Data Quality Report\n"]
    md_content.append("## Core Entities")
    md_content.append(f"- Authors: {stats.get('number_of_authors', 0)}")
    md_content.append(f"- Exposés: {stats.get('number_of_exposes', 0)}")
    md_content.append(f"- Drafts: {stats.get('number_of_drafts', 0)}")
    md_content.append(f"- Finals: {stats.get('number_of_finals', 0)}")
    md_content.append(f"- Reviews: {stats.get('number_of_reviews', 0)}")
    md_content.append(f"- Annotations: {stats.get('number_of_annotations', 0)}")
    md_content.append(f"- Comments: {stats.get('number_of_comments', 0)}")
    
    md_content.append("\n## Data Integrity")
    md_content.append(f"- Annotations without comments: {stats.get('number_of_annotations_without_comments', 0)}")
    md_content.append(f"- Comments without annotations (side comments): {stats.get('number_of_comments_without_annotations', 0)}")
    md_content.append(f"- Alignment failed: {stats.get('alignment_failed', 0)}")
    md_content.append(f"- Exact position alignments: {stats.get('alignment_exact_position', 0)}")
    md_content.append(f"- Text quote alignments: {stats.get('alignment_text_quote', 0)}")
    
    md_content.append("\n## Distributions")
    md_content.append(f"**Labels**: {json.dumps(stats.get('label_distribution', {}), indent=2)}")
    md_content.append(f"**Roles**: {json.dumps(stats.get('reviewer_role_distribution', {}), indent=2)}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "data_quality_report.md").open("w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
        
    return stats
