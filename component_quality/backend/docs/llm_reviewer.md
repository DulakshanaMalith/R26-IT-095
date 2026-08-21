# Exposía LLM Autonomous Reviewer

This documentation covers the architecture and usage of the new LLM-based autonomous reviewer.

## Architecture
The system transitions the Exposía project from a classical TF-IDF + SVM classification paradigm to a Large Language Model (LLM) reasoning paradigm. The classical SVM achieved ~0.56 Macro F1 on raw text, demonstrating that traditional bag-of-words models cannot autonomously detect academic weaknesses without human reviewer comments guiding them.

The LLM-based reviewer solves this by using zero-shot or few-shot (RAG) semantic reasoning to critique the proposal directly, extracting exact spans and providing structured reasoning.

## Review Modes
The system implements four distinct review modes to support controlled research evaluation:
1. **`legacy_svm`**: The old classical baseline. Included for backward compatibility and benchmarking.
2. **`llm_only`**: Autonomous baseline. Evaluates the text using only the LLM's pre-trained knowledge.
3. **`llm_rag`**: Exposía-grounded reviewer. Augments the LLM prompt with historical human feedback retrieved from the Exposía dataset based on semantic similarity.
4. **`llm_rag_criteria`**: Rubric-grounded reviewer. Combines RAG with the official Exposía criteria.

## LLM Provider Configuration
The system relies on the `src/reviewer/providers.py` abstraction. 
Currently supported providers:
- `OpenAIProvider` (Requires the `openai` python package)

Configuration is managed via environment variables:
- `LLM_PROVIDER`: e.g., `openai`
- `LLM_API_KEY`: API key for the chosen provider
- `LLM_MODEL`: e.g., `gpt-4o-mini`
- `LLM_TEMPERATURE`: e.g., `0.0`
- `LLM_MAX_TOKENS`: e.g., `4000`

## Evidence Validation (Hallucination Prevention)
To ensure the LLM does not invent weaknesses, the `src/reviewer/evidence.py` module runs post-generation validation. Every `Weakness` or `Strength` returned by the LLM must include an `evidence_span`. This span is string-matched against the raw proposal text. If the span is not found (even after safe normalization), the issue is silently dropped as a hallucination.

## JSON Schema Structure
The model returns a strict JSON object parsed via Pydantic (`src/reviewer/schemas.py`).
It guarantees fields like `proposal_summary`, `overall_assessment`, `issues`, and `strengths`.

## Privacy & Anonymization
RAG retrieval will strip personal author information and reviewer emails. The RAG module guarantees that when retrieving historical examples for a proposal, it completely excludes examples derived from the same author or the same proposal.
