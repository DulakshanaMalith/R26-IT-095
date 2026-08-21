#!/usr/bin/env python3
"""Entry point for the Exposía dataset processing pipeline."""

import argparse
import logging
from pathlib import Path
import sys

# Ensure src is in the python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from exposia.parsing import parse_exposes, parse_reviews
from exposia.scores import extract_criteria_hierarchy
from exposia.datasets import (
    build_normalized_tables, 
    build_master_dataset, 
    build_feedback_datasets, 
    build_scoring_datasets,
    anonymize_datasets
)
from exposia.validation import validate_datasets
from exposia.reporting import generate_quality_report
from exposia.io import write_csv, read_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Build Exposía ML datasets from raw JSON/LaTeX.")
    parser.add_argument("--input", type=str, required=True, help="Path to raw Exposía dataset directory")
    parser.add_argument("--output", type=str, required=True, help="Path to output data directory")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output directory")
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)
        
    master_dir = output_dir / "master"
    norm_dir = output_dir / "normalized"
    feedback_dir = output_dir / "feedback"
    scoring_dir = output_dir / "scoring"
    revision_dir = output_dir / "revision"
    reports_dir = output_dir.parent / "reports"
    
    if output_dir.exists() and not args.overwrite:
        logger.error(f"Output directory {output_dir} exists. Use --overwrite to replace.")
        sys.exit(1)
        
    for d in [master_dir, norm_dir, feedback_dir, scoring_dir, revision_dir, reports_dir]:
        d.mkdir(parents=True, exist_ok=True)
        
    logger.info(f"Starting Exposía dataset build from {input_dir}")
    
    # 1. Parsing
    logger.info("Parsing exposes...")
    authors_data, annotations_data1, comments_data1, scores_data1 = parse_exposes(input_dir / "exposes")
    
    logger.info("Parsing reviews...")
    reviews_data, annotations_data2, comments_data2, scores_data2 = parse_reviews(input_dir / "reviews")
    
    all_annotations = annotations_data1 + annotations_data2
    all_comments = comments_data1 + comments_data2
    all_scores = scores_data1 + scores_data2
    
    logger.info("Parsing criteria...")
    expose_c = read_json(input_dir / "supplementary" / "expose_criteria.json", {})
    review_c = read_json(input_dir / "supplementary" / "review_criteria.json", {})
    criteria_data = extract_criteria_hierarchy(expose_c, review_c)
    
    # 2. Build Normalized Tables
    logger.info("Building normalized tables and extracting context spans...")
    exposes_df, reviews_df, annotations_df, comments_df, scores_df, criteria_df = build_normalized_tables(
        authors_data, reviews_data, all_annotations, all_comments, all_scores, criteria_data
    )
    
    # Anonymize identifiers if requested (Keeping it simple for this build script)
    id_map = {}
    exposes_df = anonymize_datasets(exposes_df, id_map, "author")
    reviews_df = anonymize_datasets(reviews_df, id_map, "reviewer")
    annotations_df = anonymize_datasets(annotations_df, id_map, "reviewer")
    comments_df = anonymize_datasets(comments_df, id_map, "reviewer")
    scores_df = anonymize_datasets(scores_df, id_map, "grader")
    
    # Write Normalized
    logger.info("Writing normalized datasets...")
    exposes_df.to_csv(norm_dir / "exposes.csv", index=False)
    reviews_df.to_csv(norm_dir / "reviews.csv", index=False)
    annotations_df.to_csv(norm_dir / "annotations.csv", index=False)
    comments_df.to_csv(norm_dir / "comments.csv", index=False)
    scores_df.to_csv(norm_dir / "scores.csv", index=False)
    criteria_df.to_csv(norm_dir / "criteria.csv", index=False)
    
    # 3. Build Master
    logger.info("Building master dataset...")
    master_df = build_master_dataset(exposes_df, reviews_df, annotations_df, comments_df)
    
    master_df.to_csv(master_dir / "exposia_master.csv", index=False)
    try:
        master_df.to_parquet(master_dir / "exposia_master.parquet", index=False)
    except Exception as e:
        logger.warning(f"Could not write Parquet (pyarrow may be missing): {e}")
        
    # 4. Build Derived
    logger.info("Building derived ML datasets...")
    multi_df, bin_df, w_vs_s_df = build_feedback_datasets(master_df)
    multi_df.to_csv(feedback_dir / "feedback_multiclass.csv", index=False)
    bin_df.to_csv(feedback_dir / "feedback_binary.csv", index=False)
    w_vs_s_df.to_csv(feedback_dir / "weakness_vs_strength.csv", index=False)
    
    prog_df = build_scoring_datasets(scores_df)
    prog_df.to_csv(scoring_dir / "expose_score_progression.csv", index=False)
    
    review_scoring_df = reviews_df.copy()
    review_scoring_df.to_csv(scoring_dir / "review_scoring.csv", index=False)
    
    # Feedback -> Revision dataset (Placeholder logic as full text diffing is complex)
    # We will just write a structural CSV with "unavailable" alignment where not supported.
    rev_df = master_df[["author", "review_id", "reviewer_role", "annotation_id", "span_text", "comment_text", "annotation_tag", "draft_text", "final_text"]].copy()
    rev_df["revision_text"] = ""
    rev_df["revision_alignment_status"] = "unavailable"
    rev_df.to_csv(revision_dir / "feedback_revision.csv", index=False)
    
    # 5. Validation and Reporting
    logger.info("Running validation and audits...")
    issues = validate_datasets(master_df, annotations_df, comments_df)
    write_csv(reports_dir / "join_validation.csv", issues)
    
    stats = generate_quality_report(
        master_df, exposes_df, reviews_df, annotations_df, comments_df, scores_df, reports_dir
    )
    
    logger.info("\nExposía dataset build complete.")
    logger.info(f"Authors: {stats.get('number_of_authors')}")
    logger.info(f"Exposés: {stats.get('number_of_exposes')}")
    logger.info(f"Drafts: {stats.get('number_of_drafts')}")
    logger.info(f"Finals: {stats.get('number_of_finals')}")
    logger.info(f"Reviews: {stats.get('number_of_reviews')}")
    logger.info(f"Annotations: {stats.get('number_of_annotations')}")
    logger.info(f"Comments: {stats.get('number_of_comments')}")
    logger.info("\nOutput files generated successfully.")

if __name__ == "__main__":
    main()
