"""Deterministic document-type validation for research proposal workflows."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


MIN_PROPOSAL_WORDS = 80
VALID_CONFIDENCE_THRESHOLD = 0.58


SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [r"\babstract\b", r"\bexecutive summary\b"],
    "introduction": [r"\bintroduction\b", r"\bbackground\b"],
    "research_gap": [r"\bresearch gap\b", r"\bproblem statement\b", r"\bresearch problem\b"],
    "objectives": [r"\bobjectives?\b", r"\baims?\b", r"\bresearch questions?\b"],
    "methodology": [r"\bmethodology\b", r"\bmethods?\b", r"\bresearch design\b"],
    "literature_review": [r"\bliterature review\b", r"\brelated work\b", r"\bprevious studies\b"],
    "evaluation": [r"\bevaluation\b", r"\bvalidation\b", r"\btesting\b", r"\bmetrics?\b"],
    "expected_outcomes": [r"\bexpected outcomes?\b", r"\bdeliverables?\b", r"\bcontributions?\b"],
    "references": [r"\breferences\b", r"\bbibliography\b"],
    "timeline": [r"\bgantt\b", r"\btimeline\b", r"\bwork breakdown\b", r"\bwbs\b"],
    "ethics": [r"\bethics?\b", r"\bethical\b", r"\bconsent\b", r"\bprivacy\b"],
}

SECTION_HEADING_TERMS: dict[str, list[str]] = {
    "abstract": ["abstract", "executive summary"],
    "introduction": ["introduction", "background"],
    "research_gap": ["research gap", "problem statement", "research problem"],
    "objectives": ["objective", "objectives", "aim", "aims", "research question", "research questions"],
    "methodology": ["methodology", "method", "methods", "research design"],
    "literature_review": [
        "literature review",
        "literature survey",
        "background literature survey",
        "background & literature survey",
        "related work",
        "previous studies",
    ],
    "evaluation": ["evaluation", "evaluation strategy", "validation", "testing"],
    "expected_outcomes": ["expected outcome", "expected outcomes", "deliverables", "contributions"],
    "references": ["references", "bibliography"],
    "timeline": ["gantt", "timeline", "work breakdown", "wbs"],
    "ethics": ["ethics", "ethical considerations", "consent", "privacy"],
    "limitations": ["limitations", "constraints"],
    "conclusion": ["conclusion", "summary"],
    "system_architecture": ["system architecture", "architecture", "proposed system"],
}

IMPORTANT_SECTIONS = [
    "abstract",
    "introduction",
    "objectives",
    "research_gap",
    "methodology",
    "literature_review",
    "evaluation",
]

RESEARCH_KEYWORDS = [
    "research problem",
    "research question",
    "problem statement",
    "research gap",
    "objective",
    "objectives",
    "methodology",
    "literature review",
    "related work",
    "data collection",
    "dataset",
    "participants",
    "sample",
    "system architecture",
    "evaluation strategy",
    "evaluation",
    "validation",
    "metrics",
    "hypothesis",
    "expected outcome",
    "limitations",
    "references",
    "ethical",
    "consent",
    "contribution",
    "novelty",
]

KEYWORD_GROUPS: dict[str, list[str]] = {
    "problem_context": ["research problem", "problem statement", "research gap", "limitations"],
    "aims": ["objective", "objectives", "research question", "hypothesis"],
    "method": ["methodology", "research design", "data collection", "participants", "sample"],
    "evidence": ["literature review", "related work", "references", "ethical", "consent"],
    "evaluation": ["evaluation", "evaluation strategy", "validation", "metrics", "expected outcome"],
}

DOMAIN_KEYWORDS = [
    "research",
    "study",
    "proposal",
    "exposé",
    "expose",
    "analysis",
    "framework",
    "method",
    "methodology",
    "literature",
    "evidence",
    "experiment",
    "survey",
    "interview",
    "prototype",
    "baseline",
    "accuracy",
    "precision",
    "recall",
]

NEGATIVE_SIGNAL_PATTERNS: dict[str, list[str]] = {
    "cloud_lab_report": [
        r"\baws\b",
        r"\bec2\b",
        r"\bamazon web services\b",
        r"\bsecurity group\b",
        r"\bvpc\b",
        r"\bsubnet\b",
        r"\bs3 bucket\b",
        r"\biam\b",
        r"\belastic ip\b",
        r"\bcloudformation\b",
        r"\binstance type\b",
    ],
    "technical_tutorial": [
        r"\bstep\s+\d+\b",
        r"\bclick\b",
        r"\bconfigure\b",
        r"\bterminal\b",
        r"\bcommand prompt\b",
        r"\bpowershell\b",
        r"\bscreenshot\b",
        r"\boutput screen\b",
        r"\binstallation\b",
    ],
    "source_code": [
        r"\bimport react\b",
        r"\bconsole\.log\b",
        r"\bpublic static void\b",
        r"\bselect \* from\b",
        r"\bfunction\s+[a-z_][a-z0-9_]*\s*\(",
        r"\bclass\s+[a-z_][a-z0-9_]*\s*[:{]",
    ],
    "administrative_document": [
        r"\binvoice\b",
        r"\breceipt\b",
        r"\bpurchase order\b",
        r"\bbank statement\b",
        r"\btax invoice\b",
        r"\bcurriculum vitae\b",
        r"\bresume\b",
        r"\bcover letter\b",
        r"\bmeeting minutes\b",
    ],
}


@dataclass
class ProposalValidationResult:
    """Structured proposal-likeness validation result."""

    is_valid_proposal: bool
    confidence: float
    status: str
    word_count: int
    detected_sections: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    negative_signals: list[str] = field(default_factory=list)
    keyword_groups: dict[str, list[str]] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation payload."""
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 2)
        return payload


def normalize_text(text: str) -> str:
    """Normalize text for deterministic rule matching."""
    lowered = str(text or "").lower()
    lowered = re.sub(r"[\x00-\x1f\x7f]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def token_count(normalized_text: str) -> int:
    """Count word-like tokens."""
    return len(re.findall(r"\b[a-z0-9][a-z0-9'-]*\b", normalized_text))


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    """Match a normalized keyword as either a phrase or a whole word."""
    normalized_phrase = " ".join(re.findall(r"[a-z0-9]+", phrase.lower()))
    if not normalized_phrase:
        return False
    if " " in normalized_phrase:
        return normalized_phrase in normalized_text
    return re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_text) is not None


def heading_term_present(normalized_text: str, term: str) -> bool:
    """Return True when a proposal section term appears like a heading."""
    term_words = re.findall(r"[a-z0-9]+", term.lower())
    if not term_words:
        return False
    term_pattern = r"\W+".join(re.escape(word) for word in term_words)
    flattened_body_starts = (
        "this",
        "the",
        "there",
        "in",
        "we",
        "our",
        "existing",
        "previous",
        "proposed",
        "current",
        "research",
        "study",
        "project",
        "method",
        "methods",
        "objectives",
        "aims",
        "evaluation",
    )
    body_start_pattern = "|".join(re.escape(word) for word in flattened_body_starts)
    page_marker_prefix = r"\d+\s*(?:\|\s*)?(?:p\s*a\s*g\s*e|page)\s+"
    heading_patterns = [
        rf"(?:^|[\n\r]|[.!?]\s+|[•\u2022]\s*)\s*(?:\d+(?:\.\d+)*\.?\s+)?{term_pattern}\s*[:\-]",
        rf"(?:^|\s)\d+(?:\.\d+)*\.?\s+{term_pattern}\b",
        rf"(?:^|[\n\r])\s*{term_pattern}\s*(?:[\n\r]|$)",
        rf"(?:^|[\n\r]|[.!?]\s+|[\u2022]\s*)\s*(?:\d+(?:\.\d+)*\.?\s+)?{term_pattern}\s+(?=(?:{body_start_pattern})\b)",
        rf"(?:^|[\n\r])\s*{page_marker_prefix}{term_pattern}\s*[:\-]",
        rf"(?:^|[\n\r])\s*{page_marker_prefix}{term_pattern}\s+(?=(?:{body_start_pattern})\b)",
    ]
    return any(re.search(pattern, normalized_text, flags=re.IGNORECASE) for pattern in heading_patterns)


def detect_sections(normalized_text: str) -> list[str]:
    """Detect proposal sections from heading-like labels, not casual mentions."""
    detected: list[str] = []
    for section, terms in SECTION_HEADING_TERMS.items():
        if any(heading_term_present(normalized_text, term) for term in terms):
            detected.append(section)
    return detected


def detect_negative_signals(normalized_text: str) -> list[str]:
    """Detect unrelated document patterns that commonly fool generic keyword checks."""
    signals: list[str] = []
    for category, patterns in NEGATIVE_SIGNAL_PATTERNS.items():
        hits = sum(1 for pattern in patterns if re.search(pattern, normalized_text, flags=re.IGNORECASE))
        if hits:
            signals.append(f"{category}:{hits}")
    return signals


SECTION_ABSENCE_TERMS = [
    "without",
    "missing",
    "removed",
    "absent",
    "not provided",
    "not included",
    "does not include",
    "lacks",
]


def section_context_is_absent(normalized_text: str, start: int, end: int) -> bool:
    """Avoid treating explicit missing-section statements as detected sections."""
    context_start = max(0, start - 45)
    context_end = min(len(normalized_text), end + 45)
    context = normalized_text[context_start:context_end]
    return any(term in context for term in SECTION_ABSENCE_TERMS)


def flattened_section_present(normalized_text: str, term: str) -> bool:
    """Find section labels that survived PDF extraction only as inline text."""
    normalized_term = " ".join(re.findall(r"[a-z0-9]+", term.lower()))
    if not normalized_term:
        return False
    pattern = rf"\b{re.escape(normalized_term)}\b"
    for match in re.finditer(pattern, normalized_text, flags=re.IGNORECASE):
        if not section_context_is_absent(normalized_text, match.start(), match.end()):
            return True
    return False


def detect_flattened_sections(normalized_text: str) -> list[str]:
    """Detect likely section labels in long PDF-flattened proposal text."""
    detected: list[str] = []
    for section, terms in SECTION_HEADING_TERMS.items():
        if any(flattened_section_present(normalized_text, term) for term in terms):
            detected.append(section)
    return detected


def detect_keyword_groups(normalized_text: str) -> dict[str, list[str]]:
    """Group matched research evidence by proposal intent."""
    groups: dict[str, list[str]] = {}
    for group, keywords in KEYWORD_GROUPS.items():
        matches = [keyword for keyword in keywords if contains_phrase(normalized_text, keyword)]
        if matches:
            groups[group] = matches
    return groups


def validate_proposal_document(text: str) -> ProposalValidationResult:
    """Score whether text looks like an academic research proposal/exposé."""
    normalized_text = normalize_text(text)
    section_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", str(text or "").lower())
    section_text = re.sub(r"[ \t]+", " ", section_text)
    word_count = token_count(normalized_text)
    detected_sections = detect_sections(section_text)
    matched_keywords = [keyword for keyword in RESEARCH_KEYWORDS if contains_phrase(normalized_text, keyword)]
    keyword_groups = detect_keyword_groups(normalized_text)
    domain_matches = [keyword for keyword in DOMAIN_KEYWORDS if contains_phrase(normalized_text, keyword)]
    negative_signals = detect_negative_signals(normalized_text)
    negative_count = sum(int(signal.rsplit(":", 1)[-1]) for signal in negative_signals)
    has_flattened_proposal_evidence = (
        word_count >= 150
        and len(keyword_groups) >= 4
        and len(matched_keywords) >= 7
        and len(domain_matches) >= 5
        and negative_count < 4
    )
    if len(detected_sections) < 2 and has_flattened_proposal_evidence:
        detected_sections = sorted(set(detected_sections + detect_flattened_sections(normalized_text)))
    missing_sections = [section for section in IMPORTANT_SECTIONS if section not in detected_sections]

    length_confidence = min(word_count / 800, 1.0)
    if word_count >= 300:
        length_confidence = max(length_confidence, 0.8)
    elif word_count >= 150:
        length_confidence = max(length_confidence, 0.55)
    elif word_count >= MIN_PROPOSAL_WORDS:
        length_confidence = max(length_confidence, 0.35)

    structural_confidence = min(len(detected_sections) / 5, 1.0)
    keyword_confidence = min(len(matched_keywords) / 9, 1.0)
    domain_confidence = min(len(domain_matches) / 8, 1.0)
    negative_penalty = min(0.55, negative_count * 0.08)

    confidence = (
        0.22 * length_confidence
        + 0.35 * structural_confidence
        + 0.25 * keyword_confidence
        + 0.18 * domain_confidence
        - negative_penalty
    )
    confidence = max(0.0, min(1.0, confidence))

    reasons: list[str] = []
    warnings: list[str] = []
    if word_count >= MIN_PROPOSAL_WORDS:
        reasons.append("Sufficient document length")
    else:
        warnings.append(f"Document is too short for reliable proposal analysis ({word_count} words)")
    if detected_sections:
        reasons.append(f"{len(detected_sections)} proposal section(s) detected")
    else:
        warnings.append("No recognizable research proposal sections detected")
    if len(matched_keywords) >= 4:
        reasons.append("Research-proposal keyword coverage detected")
    else:
        warnings.append("Weak research-proposal keyword coverage")
    if len(domain_matches) >= 4:
        reasons.append("Academic/research domain language detected")
    if len(keyword_groups) >= 4:
        reasons.append("Multiple research-proposal keyword groups detected")
    if negative_signals:
        warnings.append("Unrelated document signals detected: " + ", ".join(negative_signals))

    has_required_structure = len(detected_sections) >= 2 and (
        "methodology" in detected_sections
        or "objectives" in detected_sections
        or "research_gap" in detected_sections
    )
    has_research_language = len(matched_keywords) >= 4 and len(domain_matches) >= 3
    negative_block = negative_count >= 4 and len(detected_sections) < 4
    is_valid = (
        word_count >= MIN_PROPOSAL_WORDS
        and (has_required_structure or has_flattened_proposal_evidence)
        and has_research_language
        and confidence >= VALID_CONFIDENCE_THRESHOLD
        and not negative_block
    )
    status = "valid" if is_valid else "rejected"
    if is_valid and confidence < 0.72:
        status = "warning"
        warnings.append("Proposal-likeness is acceptable but not strong")

    return ProposalValidationResult(
        is_valid_proposal=is_valid,
        confidence=confidence,
        status=status,
        word_count=word_count,
        detected_sections=detected_sections,
        missing_sections=missing_sections,
        matched_keywords=matched_keywords,
        negative_signals=negative_signals,
        keyword_groups=keyword_groups,
        reasons=reasons,
        warnings=warnings,
    )
