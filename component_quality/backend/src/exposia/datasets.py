"""Dataset construction and normalization."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
import logging

from .alignment import extract_context

logger = logging.getLogger(__name__)

def build_normalized_tables(
    authors_data: List[Dict[str, Any]], 
    reviews_data: List[Dict[str, Any]], 
    annotations_data: List[Dict[str, Any]], 
    comments_data: List[Dict[str, Any]],
    scores_data: List[Dict[str, Any]],
    criteria_data: List[Dict[str, Any]]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    
    exposes_df = pd.DataFrame(authors_data) if authors_data else pd.DataFrame(columns=["author", "topic", "draft_text", "final_text"])
    reviews_df = pd.DataFrame(reviews_data) if reviews_data else pd.DataFrame(columns=["review_hash", "author", "reviewer", "role", "group", "topic", "review_text"])
    scores_df = pd.DataFrame(scores_data) if scores_data else pd.DataFrame(columns=["author", "submission_type", "grader", "role", "group", "review_hash", "criterion", "score"])
    criteria_df = pd.DataFrame(criteria_data) if criteria_data else pd.DataFrame(columns=["criteria_type", "rubric", "criterion", "code", "description", "max_points", "min_points"])
    
    # Process annotations
    processed_anns = []
    for ann in annotations_data:
        # Resolve author context
        author = ann.get("source_author")
        if not author and ann.get("source_review_hash"):
            # Try to lookup author from reviews
            review_match = [r for r in reviews_data if r.get("review_hash") == ann.get("source_review_hash")]
            if review_match:
                author = review_match[0].get("author")
        
        # Resolve text alignment
        doc_text = ""
        if author:
            # We assume annotations target the draft text by default
            author_match = [a for a in authors_data if a.get("author") == author]
            if author_match:
                doc_text = author_match[0].get("draft_text", "")
                
        selectors_dict = ann.get("selectors") or {}
        selectors = selectors_dict.get("target", [])
        if selectors and isinstance(selectors, list):
            selectors = selectors[0].get("selector", [])
            
        alignment = extract_context(selectors, doc_text)
        
        processed_anns.append({
            "annotation_id": ann.get("id"),
            "author": author,
            "reviewer": ann.get("user"),
            "reviewer_role": ann.get("role"),
            "group": ann.get("group"),
            "review_id": ann.get("review"),
            "source_review_hash": ann.get("source_review_hash"),
            "annotation_tag": ann.get("tag"),
            "original_text": ann.get("text"),
            "span_text": alignment.span_text,
            "context_before": alignment.context_before,
            "context_after": alignment.context_after,
            "alignment_status": alignment.alignment_status
        })
        
    annotations_df = pd.DataFrame(processed_anns) if processed_anns else pd.DataFrame(columns=["annotation_id", "author", "reviewer", "reviewer_role", "group", "review_id", "annotation_tag", "span_text", "context_before", "context_after", "alignment_status"])
    
    # Process comments
    processed_comments = []
    for c in comments_data:
        processed_comments.append({
            "comment_id": c.get("id"),
            "annotation_id": c.get("annotationId"),
            "author": c.get("source_author"),
            "reviewer": c.get("user"),
            "reviewer_role": c.get("role"),
            "group": c.get("group"),
            "review_id": c.get("review"),
            "comment_text": c.get("text"),
            "comment_tags": c.get("tags", []),
            "comment_parent_id": c.get("parentCommendId"),
            "comment_votes": c.get("votes", [])
        })
        
    comments_df = pd.DataFrame(processed_comments) if processed_comments else pd.DataFrame(columns=["comment_id", "annotation_id", "author", "reviewer", "reviewer_role", "group", "review_id", "comment_text", "comment_tags", "comment_parent_id", "comment_votes"])
    
    return exposes_df, reviews_df, annotations_df, comments_df, scores_df, criteria_df


def build_master_dataset(
    exposes_df: pd.DataFrame, 
    reviews_df: pd.DataFrame, 
    annotations_df: pd.DataFrame, 
    comments_df: pd.DataFrame
) -> pd.DataFrame:
    """Build the denormalized master dataset joining annotations, comments, and exposes."""
    
    if annotations_df.empty or comments_df.empty:
        return pd.DataFrame()
        
    # Left join annotations -> comments (preserves annotations without comments)
    master_df = pd.merge(
        annotations_df, 
        comments_df, 
        on="annotation_id", 
        how="left", 
        suffixes=("", "_comment")
    )
    
    # Find side comments (comments where annotation_id is null/missing in annotations_df)
    ann_ids = set(annotations_df["annotation_id"].dropna())
    side_comments = comments_df[~comments_df["annotation_id"].isin(ann_ids)].copy()
    if not side_comments.empty:
        # Append them to master
        master_df = pd.concat([master_df, side_comments], ignore_index=True)
        
    # Coalesce author and reviewer fields
    def coalesce(col_name: str):
        if col_name in master_df.columns and f"{col_name}_comment" in master_df.columns:
            master_df[col_name] = master_df[col_name].fillna(master_df[f"{col_name}_comment"])
            
    for col in ["author", "reviewer", "reviewer_role", "group", "review_id"]:
        coalesce(col)
    
    # Clean up redundant columns
    cols_to_drop = [c for c in master_df.columns if c.endswith("_comment")]
    master_df = master_df.drop(columns=cols_to_drop)
    
    # Join with Exposes to get draft/final text
    if not exposes_df.empty:
        master_df = pd.merge(
            master_df,
            exposes_df[["author", "topic", "draft_text", "final_text"]],
            on="author",
            how="left"
        )
        
    return master_df


def build_feedback_datasets(master_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Derive feedback_multiclass, feedback_binary, and weakness_vs_strength."""
    if master_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
    # Required columns
    base_cols = ["author", "topic", "review_id", "reviewer_role", "annotation_id", "comment_id", 
                 "span_text", "context_before", "context_after", "comment_text", 
                 "annotation_tag", "comment_tags", "alignment_status"]
                 
    # Ensure columns exist
    for col in base_cols:
        if col not in master_df.columns:
            master_df[col] = None
            
    feedback_df = master_df[base_cols].copy()
    
    # Drop rows that don't have an annotation tag (e.g. pure side-comments without tags)
    feedback_df = feedback_df.dropna(subset=["annotation_tag"])
    
    # Create controlled inputs
    feedback_df["input_span"] = feedback_df["span_text"].fillna("")
    feedback_df["input_span_context"] = feedback_df["context_before"].fillna("") + " " + feedback_df["span_text"].fillna("") + " " + feedback_df["context_after"].fillna("")
    feedback_df["input_span_comment"] = feedback_df["span_text"].fillna("") + " [SEP] " + feedback_df["comment_text"].fillna("")
    feedback_df["input_full_context_comment"] = feedback_df["input_span_context"] + " [SEP] " + feedback_df["comment_text"].fillna("")
    
    # Cleanup whitespace
    for col in ["input_span", "input_span_context", "input_span_comment", "input_full_context_comment"]:
        feedback_df[col] = feedback_df[col].str.replace(r"\s+", " ", regex=True).str.strip()
        
    # Multiclass
    multiclass_df = feedback_df.copy()
    
    # Binary
    binary_df = feedback_df.copy()
    binary_df["annotation_tag"] = np.where(binary_df["annotation_tag"] == "Weakness", "Weakness", "Non-Weakness")
    
    # Weakness vs Strength
    w_vs_s_df = feedback_df[feedback_df["annotation_tag"].isin(["Weakness", "Strength"])].copy()
    
    return multiclass_df, binary_df, w_vs_s_df


def build_scoring_datasets(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Derive expose_score_progression."""
    if scores_df.empty:
        return pd.DataFrame()
        
    # Pivot draft vs final
    draft_scores = scores_df[scores_df["submission_type"] == "draft"].copy()
    final_scores = scores_df[scores_df["submission_type"] == "final"].copy()
    
    merged = pd.merge(
        draft_scores[["author", "criterion", "score"]],
        final_scores[["author", "criterion", "score"]],
        on=["author", "criterion"],
        suffixes=("_draft", "_final")
    )
    
    # Convert to numeric safely
    merged["draft_score"] = pd.to_numeric(merged["score_draft"], errors="coerce")
    merged["final_score"] = pd.to_numeric(merged["score_final"], errors="coerce")
    
    merged["score_improvement"] = merged["final_score"] - merged["draft_score"]
    
    progression_df = merged[["author", "criterion", "draft_score", "final_score", "score_improvement"]].dropna(subset=["score_improvement"])
    
    return progression_df


def anonymize_datasets(df: pd.DataFrame, id_map: dict, id_prefix: str) -> pd.DataFrame:
    """Replace sensitive names with anonymized IDs in a DataFrame."""
    if df is None or df.empty:
        return df
        
    df_clean = df.copy()
    
    for col in ["author", "reviewer", "grader"]:
        if col in df_clean.columns:
            # Map existing names to IDs, creating new ones if necessary
            df_clean[col] = df_clean[col].apply(
                lambda x: id_map.setdefault(x, f"{id_prefix}_{len(id_map):03d}") if pd.notna(x) and x != "" else x
            )
            
    return df_clean
