import argparse
import json
import logging
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        
    def handle_data(self, data):
        self.result.append(data)
        
    def get_text(self):
        return "".join(self.result)

def extract_html_text(html_content: str) -> str:
    """Extract clean text from an HTML string."""
    try:
        extractor = HTMLTextExtractor()
        extractor.feed(html_content)
        return extractor.get_text()
    except Exception as e:
        logger.warning(f"HTML extraction failed: {e}")
        return ""

def extract_latex_text(latex_content: str) -> str:
    """
    Extract meaningful text from LaTeX, stripping common commands.
    This is a heuristic extraction meant for preserving semantic academic text.
    """
    # Remove comments
    text = re.sub(r'%.*?\n', '\n', latex_content)
    # Remove begin/end environment tags
    text = re.sub(r'\\begin\{.*?\}', '', text)
    text = re.sub(r'\\end\{.*?\}', '', text)
    # Remove some common structural commands but keep their content if possible
    # E.g. \section{Introduction} -> Introduction
    text = re.sub(r'\\[a-zA-Z]+\*?\{(.*?)\}', r'\1', text)
    # Remove leftover backslash commands
    text = re.sub(r'\\[a-zA-Z]+\*?', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_text(text: str) -> str:
    """Basic text cleaning for model training."""
    if not isinstance(text, str):
        return ""
    # Normalize line endings and whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def process_exposes(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """
    Process the raw Exposes directory and build the datasets.
    """
    exposes_dir = raw_dir / "exposes"
    if not exposes_dir.exists():
        logger.error(f"Exposes directory not found at: {exposes_dir}")
        sys.exit(1)
        
    weakness_records = []
    grading_records = []
    feedback_records = []
    
    stats = {
        "authors_processed": 0,
        "annotations_extracted": 0,
        "scores_extracted": 0,
        "failed_extractions": 0,
        "empty_text_records": 0
    }
    
    # Traverse author directories
    for author_dir in sorted(exposes_dir.iterdir()):
        if not author_dir.is_dir():
            continue
            
        author = author_dir.name
        stats["authors_processed"] += 1
        
        # 1. Process Annotations (Weakness Dataset & Feedback Corpus)
        annotations_file = author_dir / "annotations.json"
        if annotations_file.exists():
            try:
                with annotations_file.open("r", encoding="utf-8") as f:
                    annotations = json.load(f)
                    
                for ann in annotations:
                    text = clean_text(ann.get("text", ""))
                    if not text:
                        stats["empty_text_records"] += 1
                        continue
                        
                    tag = ann.get("tag")
                    # For weakness classification, we need legitimate tags
                    if tag in ["Highlight", "Strength", "Weakness", "Other"]:
                        weakness_records.append({
                            "author": author,
                            "text": text,
                            "tag": tag,
                            "label": 1 if tag == "Weakness" else 0
                        })
                        stats["annotations_extracted"] += 1
                        
                        # Build Feedback Corpus for RAG if there is a comment
                        # We use 'Other' or 'Weakness' or anything that has a comment text
                        # Wait, annotations might not have 'comment_text' directly, let's check structure
                        # It might be in comments.json or in the annotation itself if flattened.
                        pass
            except Exception as e:
                logger.error(f"Failed to process annotations for {author}: {e}")
                stats["failed_extractions"] += 1

        # Process Comments (Feedback Corpus)
        comments_file = author_dir / "comments.json"
        if comments_file.exists() and annotations_file.exists():
            try:
                with comments_file.open("r", encoding="utf-8") as f:
                    comments = json.load(f)
                with annotations_file.open("r", encoding="utf-8") as f:
                    annotations = json.load(f)
                    
                # Map annotation id to text and tag
                ann_map = {a.get("id"): a for a in annotations if a.get("id")}
                
                for comment in comments:
                    ann_id = comment.get("annotationId") or comment.get("annotation_id") or comment.get("annotation")
                    if not ann_id or ann_id not in ann_map:
                        continue
                        
                    ann_data = ann_map[ann_id]
                    ann_text = clean_text(ann_data.get("text", ""))
                    comment_text = clean_text(comment.get("text", ""))
                    
                    if ann_text and comment_text:
                        feedback_records.append({
                            "author": author,
                            "annotated_text": ann_text,
                            "comment_text": comment_text,
                            "tag": ann_data.get("tag", "Unknown")
                        })
            except Exception as e:
                logger.error(f"Failed to process comments for {author}: {e}")
                stats["failed_extractions"] += 1
                
        # 2. Process Scores (Semantic Grading Dataset)
        scores_file = author_dir / "scores.json"
        if scores_file.exists():
            try:
                with scores_file.open("r", encoding="utf-8") as f:
                    scores = json.load(f)
                    
                for score_record in scores:
                    score_type = score_record.get("type")
                    if score_type not in ["draft", "final"]:
                        continue # Skip review scores as they grade the review, not the expose
                        
                    # Extract the total score
                    total_score = None
                    s_data = score_record.get("scores", {})
                    if "total" in s_data:
                        total_score = s_data["total"]
                        
                    if total_score is None:
                        continue
                        
                    # Read the corresponding document text
                    doc_dir = author_dir / score_type
                    doc_text = ""
                    
                    if doc_dir.exists():
                        tex_files = list(doc_dir.glob("*.tex"))
                        if tex_files:
                            with tex_files[0].open("r", encoding="utf-8", errors="ignore") as tf:
                                doc_text = extract_latex_text(tf.read())
                    
                    doc_text = clean_text(doc_text)
                    if not doc_text:
                        stats["empty_text_records"] += 1
                        continue
                        
                    grading_records.append({
                        "author": author,
                        "type": score_type,
                        "text": doc_text,
                        "score": total_score
                    })
                    stats["scores_extracted"] += 1
            except Exception as e:
                logger.error(f"Failed to process scores for {author}: {e}")
                stats["failed_extractions"] += 1

    df_weakness = pd.DataFrame(weakness_records)
    df_grading = pd.DataFrame(grading_records)
    df_feedback = pd.DataFrame(feedback_records)
    
    return df_weakness, df_grading, df_feedback, stats

def main():
    parser = argparse.ArgumentParser(description="Preprocess Exposía dataset for ML training.")
    parser.add_argument("--raw-dir", type=str, default="../data/raw", help="Path to raw dataset.")
    parser.add_argument("--processed-dir", type=str, default="../data/processed", help="Path to save CSVs.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism.")
    args = parser.parse_args()

    # Resolve paths relative to script location if they aren't absolute
    script_dir = Path(__file__).resolve().parent
    raw_dir = Path(args.raw_dir)
    if not raw_dir.is_absolute():
        raw_dir = (script_dir / raw_dir).resolve()
        
    processed_dir = Path(args.processed_dir)
    if not processed_dir.is_absolute():
        processed_dir = (script_dir / processed_dir).resolve()

    logger.info(f"Raw data directory: {raw_dir}")
    logger.info(f"Processed data directory: {processed_dir}")

    processed_dir.mkdir(parents=True, exist_ok=True)

    df_weakness, df_grading, df_feedback, stats = process_exposes(raw_dir)

    # Save to CSV
    weakness_path = processed_dir / "weakness_dataset.csv"
    grading_path = processed_dir / "grading_dataset.csv"
    feedback_path = processed_dir / "feedback_corpus.csv"

    if not df_weakness.empty:
        df_weakness.to_csv(weakness_path, index=False)
        logger.info(f"Saved weakness dataset: {weakness_path} ({len(df_weakness)} records)")
    else:
        logger.warning("No records found for weakness dataset.")

    if not df_grading.empty:
        df_grading.to_csv(grading_path, index=False)
        logger.info(f"Saved grading dataset: {grading_path} ({len(df_grading)} records)")
    else:
        logger.warning("No records found for grading dataset.")
        
    if not df_feedback.empty:
        df_feedback.to_csv(feedback_path, index=False)
        logger.info(f"Saved feedback corpus: {feedback_path} ({len(df_feedback)} records)")
    else:
        logger.warning("No records found for feedback corpus.")

    # Quality Report
    report = {
        "weakness_records": len(df_weakness),
        "grading_records": len(df_grading),
        "feedback_records": len(df_feedback),
        "weakness_label_distribution": df_weakness["tag"].value_counts().to_dict() if not df_weakness.empty else {},
        "grading_score_distribution": df_grading["score"].describe().to_dict() if not df_grading.empty else {},
        "stats": stats
    }

    report_path = processed_dir / "data_quality_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
        
    logger.info(f"Data quality report saved to {report_path}")
    logger.info(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
