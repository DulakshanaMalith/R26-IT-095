"""Alignment logic to extract robust context spans for annotations."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

@dataclass
class AlignmentResult:
    span_text: str
    context_before: str
    context_after: str
    alignment_status: str

def extract_context(
    selectors: list[dict[str, Any]], 
    document_text: str, 
    context_window: int = 100
) -> AlignmentResult:
    """Attempt to align an annotation with the full document text to extract context.
    
    Tries TextQuoteSelector first because LaTeX cleaning breaks TextPositionSelector indices.
    Falls back to TextPositionSelector, then returns failed if none work.
    """
    if not document_text:
        return AlignmentResult("", "", "", "failed")
        
    exact = ""
    prefix = ""
    suffix = ""
    
    start_idx = -1
    end_idx = -1
    
    for selector in selectors:
        stype = selector.get("type", "")
        if stype == "TextQuoteSelector":
            exact = selector.get("exact", "")
            prefix = selector.get("prefix", "")
            suffix = selector.get("suffix", "")
        elif stype == "TextPositionSelector":
            start_idx = selector.get("start", -1)
            end_idx = selector.get("end", -1)
            
    # Try 1: Exact Match in cleaned document text
    if exact:
        if exact in document_text:
            # If it's unique, we found it perfectly
            if document_text.count(exact) == 1:
                idx = document_text.find(exact)
                return _build_result(document_text, idx, idx + len(exact), exact, "text_quote", context_window)
                
            # If there are multiples, try to disambiguate with prefix/suffix
            elif prefix or suffix:
                search_str = prefix + exact + suffix
                if search_str in document_text:
                    idx = document_text.find(search_str) + len(prefix)
                    return _build_result(document_text, idx, idx + len(exact), exact, "text_quote", context_window)
        
        # Try 2: Normalized match (ignore excessive whitespace)
        norm_exact = " ".join(exact.split())
        norm_doc = " ".join(document_text.split())
        if norm_exact in norm_doc and norm_doc.count(norm_exact) == 1:
            return AlignmentResult(
                span_text=exact,
                context_before="[Normalized match before context unavailable]",
                context_after="[Normalized match after context unavailable]",
                alignment_status="normalized_match"
            )

    # Try 3: TextPositionSelector (very risky due to LaTeX cleaning)
    if start_idx >= 0 and end_idx > start_idx:
        # Check if the extracted text looks remotely like the exact quote if we have one
        pos_text = document_text[start_idx:end_idx]
        if exact and (exact[:10] in pos_text or pos_text[:10] in exact):
             return _build_result(document_text, start_idx, end_idx, pos_text, "exact_position", context_window)
        elif not exact:
             return _build_result(document_text, start_idx, end_idx, pos_text, "exact_position", context_window)
             
    # Fallback: Failed
    return AlignmentResult(
        span_text=exact if exact else "[Failed to extract]",
        context_before="",
        context_after="",
        alignment_status="failed"
    )

def _build_result(doc: str, start: int, end: int, span: str, status: str, window: int = 150) -> AlignmentResult:
    context_start = max(0, start - window)
    context_end = min(len(doc), end + window)
    return AlignmentResult(
        span_text=span,
        context_before=doc[context_start:start],
        context_after=doc[end:context_end],
        alignment_status=status
    )
