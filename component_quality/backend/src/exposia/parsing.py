"""Directory parsing and raw data collection."""

from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

from .io import read_json, read_text_file
from .text import load_submission_text
from .scores import flatten_scores

logger = logging.getLogger(__name__)

def parse_exposes(exposes_dir: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse the exposes directory to extract authors, annotations, comments, and scores."""
    authors_data = []
    annotations_data = []
    comments_data = []
    scores_data = []
    
    if not exposes_dir.exists():
        logger.warning(f"Exposes directory missing: {exposes_dir}")
        return [], [], [], []
        
    for author_dir in [d for d in exposes_dir.iterdir() if d.is_dir()]:
        meta = read_json(author_dir / "meta.json", {})
        author_name = meta.get("author") or author_dir.name
        topic = meta.get("topic", "")
        
        draft_text = load_submission_text(author_dir, "draft")
        final_text = load_submission_text(author_dir, "final")
        
        authors_data.append({
            "author": author_name,
            "topic": topic,
            "draft_text": draft_text,
            "final_text": final_text
        })
        
        # Annotations
        author_annotations = read_json(author_dir / "annotations.json", [])
        if isinstance(author_annotations, list):
            for ann in author_annotations:
                ann["source_author"] = author_name
                ann["source_type"] = "expose"
                annotations_data.append(ann)
                
        # Comments
        author_comments = read_json(author_dir / "comments.json", [])
        if isinstance(author_comments, list):
            for comment in author_comments:
                comment["source_author"] = author_name
                comment["source_type"] = "expose"
                comments_data.append(comment)
                
        # Scores
        author_scores = read_json(author_dir / "scores.json", [])
        if isinstance(author_scores, list):
            scores_data.extend(flatten_scores(author_scores))
            
    return authors_data, annotations_data, comments_data, scores_data


def parse_reviews(reviews_dir: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse the reviews directory to extract reviews, annotations, comments, and edits."""
    reviews_data = []
    annotations_data = []
    comments_data = []
    scores_data = [] # Some reviews might have scores if they use a similar structure
    
    if not reviews_dir.exists():
        logger.warning(f"Reviews directory missing: {reviews_dir}")
        return [], [], [], []
        
    for review_dir in [d for d in reviews_dir.iterdir() if d.is_dir()]:
        review_hash = review_dir.name
        meta = read_json(review_dir / "meta.json", {})
        
        # Read the review text if it exists
        review_text = read_text_file(review_dir / "review.txt")
        
        reviews_data.append({
            "review_hash": review_hash,
            "author": meta.get("author", ""),
            "reviewer": meta.get("reviewer", ""),
            "role": meta.get("role", ""),
            "group": meta.get("group", ""),
            "topic": meta.get("topic", ""),
            "review_text": review_text
        })
        
        # Annotations
        review_annotations = read_json(review_dir / "annotations.json", [])
        if isinstance(review_annotations, list):
            for ann in review_annotations:
                ann["source_review_hash"] = review_hash
                ann["source_type"] = "review"
                annotations_data.append(ann)
                
        # Comments
        review_comments = read_json(review_dir / "comments.json", [])
        if isinstance(review_comments, list):
            for comment in review_comments:
                comment["source_review_hash"] = review_hash
                comment["source_type"] = "review"
                comments_data.append(comment)
                
    return reviews_data, annotations_data, comments_data, scores_data
