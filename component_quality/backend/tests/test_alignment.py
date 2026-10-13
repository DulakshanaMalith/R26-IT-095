"""Tests for text alignment logic."""

from exposia.alignment import extract_context

def test_exact_match():
    doc = "This is a simple test document to check alignment."
    selectors = [
        {
            "type": "TextQuoteSelector",
            "exact": "simple test document"
        }
    ]
    
    result = extract_context(selectors, doc, context_window=10)
    assert result.alignment_status == "text_quote"
    assert result.span_text == "simple test document"
    assert result.context_before == "This is a "
    assert result.context_after == " to check "

def test_normalized_match():
    doc = "This is a   simple \n test document."
    selectors = [
        {
            "type": "TextQuoteSelector",
            "exact": "simple test document"
        }
    ]
    
    result = extract_context(selectors, doc, context_window=10)
    assert result.alignment_status == "normalized_match"
    assert result.span_text == "simple test document"
    
def test_failed_match():
    doc = "Something entirely different."
    selectors = [
        {
            "type": "TextQuoteSelector",
            "exact": "simple test document"
        }
    ]
    
    result = extract_context(selectors, doc)
    assert result.alignment_status == "failed"
    assert result.span_text == "simple test document"
