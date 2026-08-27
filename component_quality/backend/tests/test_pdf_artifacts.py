import pytest
from src.core.document_validator import normalize_extracted_document_text, validate_proposal_document, detect_sections, is_section_heading
from src.api.services.core_logic import calculate_sufficiency_aware_completeness

def test_normalize_pdf_artifacts():
    tests = [
        ("4 | Page\nABSTRACT\nThis paper addresses", " ABSTRACT\nThis paper addresses"),
        ("4 | Page ABSTRACT\nThis paper addresses", " ABSTRACT\nThis paper addresses"),
        ("4 Page ABSTRACT", " ABSTRACT"),
        ("4 | P a g e\nABSTRACT", " ABSTRACT"),
        ("A B S T R A C T", "ABSTRACT"),
        ("4 | P a g e A B S T R A C T", " ABSTRACT"),
        ("4 | P a g e\n\nABSTRACT\n\nThe abstract concept", " ABSTRACT\n\nThe abstract concept")
    ]
    for inp, exp in tests:
        assert normalize_extracted_document_text(inp) == exp

def test_detect_spaced_sections():
    assert "abstract" in detect_sections("4 | P a g e ABSTRACT this paper")

def test_sufficiency_aware_completeness():
    text = "Abstract this is an abstract. " * 30 # ~120 words
    comp, ded, missing, ev, warn = calculate_sufficiency_aware_completeness(text, ["abstract"], ["introduction"])
    assert "Abstract" in ev
    assert ev["Abstract"]["heading_found"] is True
    assert ev["Abstract"]["sufficiency_percentage"] == 100
    
    # Missing heading
    assert "Introduction" in ev
    assert ev["Introduction"]["heading_found"] is False
    assert ev["Introduction"]["sufficiency_percentage"] == 0
