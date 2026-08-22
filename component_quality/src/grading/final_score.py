SEMANTIC_WEIGHT = 0.65
ML_WEIGHT = 0.35


def calculate_final_hybrid_score(semantic_score: float, ml_score: float) -> dict:
    # Semantic rubric alignment remains primary because the system is rubric-driven.
    # ML score is supportive, improving consistency without overpowering evaluator intent.
    final_score = (SEMANTIC_WEIGHT * semantic_score) + (ML_WEIGHT * ml_score)
    final_score = round(final_score, 2)

    if final_score >= 75:
        grade = "A"
        status = "Excellent"
    elif final_score >= 65:
        grade = "B"
        status = "Good"
    elif final_score >= 50:
        grade = "C"
        status = "Satisfactory"
    elif final_score >= 40:
        grade = "D"
        status = "Needs Improvement"
    else:
        grade = "F"
        status = "Unsatisfactory"

    return {
        "final_score": final_score,
        "grade": grade,
        "status": status,
        "weights": {
            "semantic": SEMANTIC_WEIGHT,
            "ml": ML_WEIGHT,
        },
    }