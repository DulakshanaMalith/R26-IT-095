"""Lightweight concept mapping for ResearchPilot proposal analysis."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.db import history_repositories


ROOT_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - keeps legacy installs usable until requirements are installed.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env")


def env_path(name: str, default: str) -> Path:
    value = os.getenv(name, default).strip() or default
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


DATA_DIR = env_path("DATA_DIR", "data")


DEFAULT_CHECKLIST = [
    "Research Question",
    "Objectives",
    "Methodology",
    "Dataset",
    "Evaluation",
    "Metrics",
    "Baseline",
    "Results",
    "Limitations",
    "Ethics",
    "Future Work",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
    "we",
    "will",
    "using",
    "use",
    "used",
    "study",
    "research",
    "proposal",
}

SPACY_INSTALL_INSTRUCTIONS = "python -m spacy download en_core_web_sm"
_NLP: Any | None = None
_SPACY_STATUS: str | None = None


def clean_input_text(text: str) -> str:
    """Validate and normalize user-provided proposal text."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string.")
    return re.sub(r"\s+", " ", text).strip()


GENERIC_CONCEPTS = {
    "list", "table", "figure", "section", "chapter", "page", "step", "method", "approach", 
    "system", "model", "data", "result", "analysis", "study", "research", "paper", "proposal", 
    "project", "work", "conclusion", "introduction", "background", "overview", "example", 
    "case", "problem", "question", "objective", "aim", "goal", "dataset", "framework",
    "part", "type", "form", "way", "idea", "concept", "context", "literature", "review"
}

def is_valid_concept(concept: str) -> bool:
    """Filter out purely numeric, too short, or malformed concepts."""
    if not concept:
        return False
    # Must contain at least one letter
    if not re.search(r'[A-Za-z]', concept):
        return False
    # Filter very short tokens unless they are known acronyms
    letters = re.sub(r'[^A-Za-z]', '', concept)
    if len(letters) < 3 and concept.upper() not in ["AI", "ML", "DL", "VR", "AR", "UI", "UX", "OS", "IT", "DB", "RQ", "F1", "RF", "NN"]:
        return False
    if concept.lower() in GENERIC_CONCEPTS:
        return False
    return True


def normalize_concept(concept: str) -> str:
    """Normalize concept text while keeping a readable display form."""
    concept = re.sub(r"[^A-Za-z0-9\s-]", " ", concept)
    # Strip leading numbers and hyphens
    concept = re.sub(r"^[\d\s-]+", "", concept)
    concept = re.sub(r"\s+", " ", concept).strip()
    return concept.title()


def normalize_and_split_concept(concept: str) -> list[str]:
    """Split merged OCR artifacts into multiple concepts, preserving legitimate tech names."""
    PRESERVE = {"mobilenet", "mobilenetv2", "tflite", "resemblyzer", "youtube", "github"}
    if concept.lower() in PRESERVE:
        return [normalize_concept(concept)]
    
    # Check if we should split camelCase.
    # Split if there's no native spaces and there's a lowercase followed by uppercase.
    split_text = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', concept)
    if ' ' not in concept and ' ' in split_text:
        # It was squashed, yield parts separately
        return [normalize_concept(w) for w in split_text.split()]
    
    return [normalize_concept(split_text)]


def concept_key(concept: str) -> str:
    """Return a stable lowercase key for de-duplicating concepts."""
    return re.sub(r"\s+", " ", concept.lower()).strip()


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-like chunks without external dependencies."""
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def load_spacy_model() -> tuple[Any | None, str | None]:
    """Load spaCy once, returning friendly instructions if unavailable."""
    global _NLP, _SPACY_STATUS
    if _NLP is not None or _SPACY_STATUS is not None:
        return _NLP, _SPACY_STATUS

    try:
        import spacy  # type: ignore

        _NLP = spacy.load("en_core_web_sm")
        _SPACY_STATUS = "available"
    except Exception:
        _NLP = None
        _SPACY_STATUS = f"spaCy model unavailable. Install it with: {SPACY_INSTALL_INSTRUCTIONS}"
    return _NLP, _SPACY_STATUS


def extract_with_spacy(text: str, max_concepts: int) -> tuple[list[str], dict[str, list[str]], str | None]:
    """Extract noun chunks and named entities with spaCy when available."""
    nlp, status = load_spacy_model()
    if nlp is None:
        return [], {}, status

    try:
        doc = nlp(text)
    except Exception:
        return [], {}, f"spaCy processing failed. If needed, reinstall the model: {SPACY_INSTALL_INSTRUCTIONS}"

    counts: Counter[str] = Counter()
    sentence_concepts: dict[str, list[str]] = {}

    for sentence in doc.sents:
        concepts_in_sentence = []
        candidates = list(sentence.noun_chunks) + list(sentence.ents)
        for candidate in candidates:
            # candidate.text could be "SaveeTess"
            parts = normalize_and_split_concept(candidate.text)
            for concept in parts:
                if not is_valid_concept(concept):
                    continue
                tokens = [token for token in concept_key(concept).split() if token not in STOPWORDS]
                if not tokens or len(" ".join(tokens)) < 3:
                    continue
                normalized = normalize_concept(" ".join(tokens))
                if not is_valid_concept(normalized):
                    continue
                counts[normalized] += 1
                concepts_in_sentence.append(normalized)

        unique_sentence_concepts = sorted(set(concepts_in_sentence), key=concepts_in_sentence.index)
        if unique_sentence_concepts:
            sentence_concepts[sentence.text] = unique_sentence_concepts

    concepts = [concept for concept, _ in counts.most_common(max_concepts)]
    return concepts, sentence_concepts, None


def extract_with_fallback(text: str, max_concepts: int) -> tuple[list[str], dict[str, list[str]]]:
    """Fallback keyword extraction using simple noun-phrase-like token windows."""
    sentences = split_sentences(text)
    counts: Counter[str] = Counter()
    sentence_concepts: dict[str, list[str]] = {}

    for sentence in sentences:
        words = [
            word.lower()
            for word in re.findall(r"[A-Za-z][A-Za-z-]{2,}", sentence)
            if word.lower() not in STOPWORDS
        ]
        candidates = []

        for size in (3, 2):
            for index in range(0, max(len(words) - size + 1, 0)):
                phrase = words[index : index + size]
                if len(set(phrase)) == 1:
                    continue
                parts = normalize_and_split_concept(" ".join(phrase))
                for concept in parts:
                    if is_valid_concept(concept):
                        candidates.append(concept)

        for word in words:
            parts = normalize_and_split_concept(word)
            for concept in parts:
                if is_valid_concept(concept):
                    candidates.append(concept)
        unique_candidates = []
        seen = set()
        for candidate in candidates:
            key = concept_key(candidate)
            if key and key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)
                counts[candidate] += 1

        if unique_candidates:
            sentence_concepts[sentence] = unique_candidates[:8]

    concepts = [concept for concept, _ in counts.most_common(max_concepts)]
    return concepts, sentence_concepts


def build_edges(
    sentence_concepts: dict[str, list[str]],
    allowed_concepts: set[str],
) -> list[dict[str, Any]]:
    """Connect concepts that appear in the same sentence."""
    edge_counts: Counter[tuple[str, str]] = Counter()
    for concepts in sentence_concepts.values():
        filtered = [
            concept
            for concept in concepts
            if concept_key(concept) in allowed_concepts
        ]
        for source, target in combinations(sorted(set(filtered)), 2):
            edge_counts[(source, target)] += 1

    return [
        {"source": source, "target": target, "weight": weight}
        for (source, target), weight in edge_counts.most_common()
    ]


def evaluate_concept_states(text: str, sentences: list[str]) -> tuple[list[str], list[str], dict[str, str]]:
    """Evaluate semantic presence (present, implicit, missing) for concepts."""
    missing_concepts = []
    implicit_concepts = []
    concept_evidence = {}
    
    def find_evidence(patterns: list[str], sentence_list: list[str]) -> str | None:
        for sent in sentence_list:
            sent_lower = sent.lower()
            if any(re.search(r'\b' + re.escape(p) + r'(s|es)?\b', sent_lower) for p in patterns):
                return sent
        return None

    PATTERNS = {
        "Research Question": {
            "present": [
                "research question", "research problem", "this study investigates", 
                "the research problem is", "how can", "what is the impact of",
                "problem statement"
            ],
            "implicit": ["research gap", "objective", "aim", "goal", "hypothesis", "problem"]
        },
        "Metrics": {
            "present": [
                "recall", "precision", "f1", "accuracy", "far", "false alarm rate", 
                "latency", "battery impact", "performance target", "evaluation threshold"
            ],
            "implicit": ["performance", "evaluate", "result", "outcome", "measurement", "metric", "measure"]
        },
        "Limitations": {
            "present": [
                "limitation", "constraint", "trade-off", "risk", "challenge", 
                "deployment issue", "threat to validity", "downside"
            ],
            "implicit": ["noise", "battery", "resource", "device constraint", "environment", "variability", "technical requirement"]
        },
        "Future Work": {
            "present": [
                "future work", "future research", "subsequent research", "post-project", 
                "future extension", "outside the scope", "beyond the scope"
            ],
            "implicit": ["future", "next step", "potential direction", "could be explored"]
        }
    }

    aliases = {
        "Objectives": ["objective", "objectives", "aim", "aims", "goal", "goals"],
        "Methodology": ["methodology", "method", "methods", "research design"],
        "Dataset": ["dataset", "data set", "data", "corpus"],
        "Evaluation": ["evaluation", "evaluate", "experiment", "assessment"],
        "Baseline": ["baseline", "comparison", "benchmark"],
        "Results": ["result", "results", "finding", "findings"],
        "Ethics": ["ethic", "ethics", "ethical", "consent", "privacy"],
    }
    
    text_lower = text.lower()
    
    for concept in DEFAULT_CHECKLIST:
        if concept in PATTERNS:
            present_evidence = None
            if concept == "Metrics":
                # Look for quantitative evidence strongly tied to metrics
                for sent in sentences:
                    sent_lower = sent.lower()
                    if any(re.search(r'\b' + re.escape(p) + r'\b', sent_lower) for p in PATTERNS[concept]["present"]):
                        if re.search(r'([<>]=?\s*\d+|\d+\s*%|\bseconds?\b|\bms\b)', sent_lower):
                            present_evidence = sent
                            break
            if not present_evidence:
                present_evidence = find_evidence(PATTERNS[concept]["present"], sentences)
                
            if present_evidence:
                concept_evidence[concept] = present_evidence
                continue
                
            implicit_evidence = find_evidence(PATTERNS[concept]["implicit"], sentences)
            if implicit_evidence:
                implicit_concepts.append(concept)
                concept_evidence[concept] = implicit_evidence
            else:
                missing_concepts.append(concept)
        else:
            if concept in aliases and not any(alias in text_lower for alias in aliases[concept]):
                missing_concepts.append(concept)
                
    return missing_concepts, implicit_concepts, concept_evidence


def analyze_knowledge_graph(text: str, max_concepts: int = 20) -> dict[str, Any]:
    """Extract concepts, build co-occurrence edges, and detect missing concepts."""
    cleaned_text = clean_input_text(text)
    sentences = split_sentences(cleaned_text)
    concepts, sentence_concepts, warning = extract_with_spacy(cleaned_text, max_concepts)

    if not concepts:
        concepts, sentence_concepts = extract_with_fallback(cleaned_text, max_concepts)

    allowed_concepts = {concept_key(concept) for concept in concepts}
    edges = build_edges(sentence_concepts, allowed_concepts)
    
    missing_concepts, implicit_concepts, concept_evidence = evaluate_concept_states(cleaned_text, sentences)
    
    result = {
        "concepts": concepts,
        "edges": edges,
        "missing_concepts": missing_concepts,
        "implicit_concepts": implicit_concepts,
        "concept_evidence": concept_evidence,
    }
    if warning:
        result["nlp_warning"] = warning
    return result


def ensure_history_file() -> None:
    """Retained for compatibility; graph histories are PostgreSQL-backed."""
    return None


def load_graph_history() -> list[dict[str, Any]]:
    """Load graph history from PostgreSQL."""
    return history_repositories.list_graph_history()


def find_graph_record_by_analysis_id(analysis_id: str | None) -> dict[str, Any] | None:
    """Return the newest graph record linked by exact analysis_id."""
    if not isinstance(analysis_id, str) or not analysis_id.strip():
        return None
    normalized_id = analysis_id.strip()
    for record in reversed(load_graph_history()):
        if isinstance(record, dict) and record.get("analysis_id") == normalized_id:
            return record
    return None


def write_graph_history(history: list[dict[str, Any]]) -> None:
    """Replace graph history records in PostgreSQL."""
    history_repositories.replace_graph_history(history)


def save_graph_history(
    *,
    analysis_id: str | None,
    filename: str | None,
    graph: dict[str, Any],
) -> dict[str, Any]:
    """Save a lightweight graph summary for demo history."""
    record = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_id": analysis_id.strip() if isinstance(analysis_id, str) and analysis_id.strip() else None,
        "filename": filename or None,
        "concept_count": len(graph.get("concepts", [])),
        "concepts": graph.get("concepts", []),
        "edges": graph.get("edges", []),
        "missing_concepts": graph.get("missing_concepts", []),
        "implicit_concepts": graph.get("implicit_concepts", []),
    }
    history_repositories.append_graph_record(record)
    return record
