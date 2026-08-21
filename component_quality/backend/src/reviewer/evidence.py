import re
import logging
from typing import Tuple

from .schemas import Issue, ReviewResult

logger = logging.getLogger(__name__)

def normalize_text(text: str) -> str:
    """Safely normalizes text for evidence matching by removing extra whitespace and lowering case."""
    if not text:
        return ""
    # Remove all whitespace runs and make lowercase
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()

def validate_evidence_span(evidence: str, proposal_text: str) -> Tuple[bool, str]:
    """
    Checks if the evidence span occurs in the proposal text.
    Returns (is_valid, validation_reason).
    """
    if not evidence or not evidence.strip():
        return False, "Evidence span is empty."
        
    # Exact match
    if evidence in proposal_text:
        return True, "Exact match found."
        
    # Normalized match
    norm_evidence = normalize_text(evidence)
    norm_proposal = normalize_text(proposal_text)
    
    if norm_evidence in norm_proposal:
        return True, "Normalized match found."
        
    return False, "Evidence span could not be found in the proposal text."

def validate_review_result(result: ReviewResult, proposal_text: str) -> ReviewResult:
    """
    Iterates through all issues in the ReviewResult and removes or marks invalid ones.
    In this implementation, we simply drop invalid weaknesses to prevent hallucinations.
    """
    valid_issues = []
    
    for issue in result.issues:
        is_valid, reason = validate_evidence_span(issue.evidence_span, proposal_text)
        if is_valid:
            valid_issues.append(issue)
        else:
            logger.warning(f"Dropped invalid issue '{issue.issue_id}': {reason}. Span: '{issue.evidence_span}'")
            
    valid_strengths = []
    for strength in result.strengths:
        is_valid, reason = validate_evidence_span(strength.evidence_span, proposal_text)
        if is_valid:
            valid_strengths.append(strength)
        else:
            logger.warning(f"Dropped invalid strength '{strength.issue_id}': {reason}. Span: '{strength.evidence_span}'")

    result.issues = valid_issues
    result.strengths = valid_strengths
    
    return result
