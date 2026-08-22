def detect_weaknesses(rubric_results: dict, threshold: float = 0.50) -> list:
    weaknesses = []

    for criterion, result in rubric_results.items():
        score = result["similarity_score"]
        compliance = result.get("compliance_level", "Unknown")

        if compliance == "Missing Section":
            weaknesses.append({
                "criterion": criterion,
                "issue": f"The expected section for '{criterion}' is missing from the report."
            })
        elif score < threshold:
            weaknesses.append({
                "criterion": criterion,
                "issue": (
                    f"Improvement needed in '{criterion}'. "
                    f"Current match score ({score:.2f}) is below the required proficiency level of {threshold:.2f}."
                )
            })

    return weaknesses