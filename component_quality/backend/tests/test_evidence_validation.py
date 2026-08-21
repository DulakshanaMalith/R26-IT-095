import sys
from pathlib import Path

# Add src to python path for relative imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reviewer.evidence import validate_evidence_span, normalize_text

def test_normalize_text():
    assert normalize_text("  Hello   World  \n") == "hello world"
    assert normalize_text("") == ""
    assert normalize_text("Exact-Match!") == "exact-match!"

def test_validate_evidence_exact_match():
    proposal = "This study aims to investigate the effects of sleep on memory. We will survey 50 students."
    evidence = "We will survey 50 students."
    is_valid, _ = validate_evidence_span(evidence, proposal)
    assert is_valid is True

def test_validate_evidence_normalized_match():
    proposal = "This study aims to investigate the effects of sleep on memory. \n  We   will survey 50 students."
    evidence = "We will survey 50 students."
    is_valid, _ = validate_evidence_span(evidence, proposal)
    assert is_valid is True

def test_validate_evidence_hallucination():
    proposal = "This study aims to investigate the effects of sleep on memory."
    evidence = "We will survey 50 students."
    is_valid, _ = validate_evidence_span(evidence, proposal)
    assert is_valid is False

def test_validate_evidence_empty():
    proposal = "This study aims to investigate the effects of sleep on memory."
    evidence = ""
    is_valid, _ = validate_evidence_span(evidence, proposal)
    assert is_valid is False
