def calculate_scores(rubric_results: dict, rubric: dict) -> dict:
    section_scores = []
    overall_score = 0.0

    for criterion in rubric["criteria"]:
        name = criterion["name"]
        weight = criterion["weight"]

        similarity_score = rubric_results.get(name, {}).get("similarity_score", 0.0)
        compliance_level = rubric_results.get(name, {}).get("compliance_level", "Unknown")

        raw_score = round(similarity_score * 100, 2)
        weighted_score = round(raw_score * weight, 2)

        section_scores.append({
            "criterion": name,
            "weight": weight,
            "similarity_score": similarity_score,
            "raw_score": raw_score,
            "weighted_score": weighted_score,
            "compliance_level": compliance_level
        })

        overall_score += weighted_score

    overall_score = round(overall_score, 2)

    if overall_score >= 75:
        grade = "A"
        status = "Excellent"
    elif overall_score >= 65:
        grade = "B"
        status = "Good"
    elif overall_score >= 50:
        grade = "C"
        status = "Satisfactory"
    elif overall_score >= 40:
        grade = "D"
        status = "Needs Improvement"
    else:
        grade = "F"
        status = "Unsatisfactory"

    return {
        "section_scores": section_scores,
        "overall_score": overall_score,
        "grade": grade,
        "status": status
    }