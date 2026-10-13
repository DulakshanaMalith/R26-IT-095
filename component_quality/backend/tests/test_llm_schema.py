import pytest
from pydantic import ValidationError
import sys
from pathlib import Path

# Add src to python path for relative imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reviewer.schemas import Issue, ReviewResult

def test_issue_schema_valid():
    valid_data = {
        "issue_id": "i001",
        "type": "Weakness",
        "severity": "high",
        "section": "Methodology",
        "criterion": "N/A",
        "evidence_span": "We will survey some people.",
        "reason": "Vague sample size.",
        "recommendation": "Specify sample size.",
        "confidence": 0.9,
        "retrieved_example_ids": []
    }
    issue = Issue(**valid_data)
    assert issue.type == "Weakness"
    assert issue.confidence == 0.9

def test_issue_schema_invalid_confidence():
    invalid_data = {
        "issue_id": "i001",
        "type": "Weakness",
        "severity": "high",
        "section": "Methodology",
        "criterion": "N/A",
        "evidence_span": "We will survey some people.",
        "reason": "Vague sample size.",
        "recommendation": "Specify sample size.",
        "confidence": 1.5, # Invalid, > 1.0
        "retrieved_example_ids": []
    }
    with pytest.raises(ValidationError):
        Issue(**invalid_data)

def test_issue_schema_invalid_severity():
    invalid_data = {
        "issue_id": "i001",
        "type": "Weakness",
        "severity": "critical", # Invalid literal
        "section": "Methodology",
        "criterion": "N/A",
        "evidence_span": "We will survey some people.",
        "reason": "Vague sample size.",
        "recommendation": "Specify sample size.",
        "confidence": 0.8,
        "retrieved_example_ids": []
    }
    with pytest.raises(ValidationError):
        Issue(**invalid_data)

def test_review_result_schema_valid():
    valid_data = {
        "proposal_summary": "Test summary.",
        "overall_assessment": "Test assessment.",
        "issues": [],
        "strengths": [],
        "criterion_results": []
    }
    rr = ReviewResult(**valid_data)
    assert rr.proposal_summary == "Test summary."
