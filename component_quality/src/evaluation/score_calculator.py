"""Evaluation-facing score calculator.

This module re-exports the hybrid scoring function so evaluation workflows
can import from src.evaluation while preserving grading implementation in
src.grading.final_score.
"""

from src.grading.final_score import (
    ML_WEIGHT,
    SEMANTIC_WEIGHT,
    calculate_final_hybrid_score,
)

__all__ = ["calculate_final_hybrid_score", "SEMANTIC_WEIGHT", "ML_WEIGHT"]
