import os
from typing import List, Dict, Any, Optional
from pathlib import Path

from .schemas import ReviewResult
from .providers import get_llm_provider
from .evidence import validate_review_result
from .retrieval import get_retriever, format_rag_examples_for_prompt
from .criteria import load_criteria_as_text

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

def run_review(
    proposal_text: str,
    mode: str = "llm_only",
    excluded_author_ids: Optional[List[str]] = None,
    top_k: int = 5
) -> tuple[ReviewResult, Dict[str, Any]]:
    """
    Executes the LLM review pipeline based on the specified mode.
    Modes:
      - llm_only
      - llm_rag
      - llm_rag_criteria
    """
    system_prompt_path = PROMPTS_DIR / "reviewer_system_v1.txt"
    user_prompt_path = PROMPTS_DIR / "reviewer_user_v1.txt"
    
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    user_prompt_template = user_prompt_path.read_text(encoding="utf-8")

    # Mode configurations
    use_rag = mode in ["llm_rag", "llm_rag_criteria"]
    use_criteria = mode == "llm_rag_criteria"

    historical_examples_block = ""
    retrieved_count = 0
    if use_rag:
        retriever = get_retriever()
        examples = retriever.retrieve_similar_feedback(
            query_text=proposal_text,
            excluded_author_ids=excluded_author_ids,
            top_k=top_k
        )
        historical_examples_block = format_rag_examples_for_prompt(examples)
        retrieved_count = len(examples)

    criteria_block = ""
    if use_criteria:
        criteria_block = load_criteria_as_text()

    # Format user prompt
    user_prompt = user_prompt_template.format(
        context_block="",
        historical_examples=historical_examples_block,
        criteria_block=criteria_block,
        proposal_text=proposal_text
    )

    provider = get_llm_provider()
    
    raw_result, metadata = provider.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=ReviewResult
    )

    # Validate evidence spans (drops hallucinations)
    validated_result = validate_review_result(raw_result, proposal_text)
    
    # Update metadata
    metadata["mode"] = mode
    metadata["retrieved_examples"] = retrieved_count
    metadata["prompt_version"] = "reviewer_v1"
    
    return validated_result, metadata
