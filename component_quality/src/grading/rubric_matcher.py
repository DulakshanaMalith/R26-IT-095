from sentence_transformers import SentenceTransformer, util


model = SentenceTransformer("all-MiniLM-L6-v2")


def score_band(similarity: float) -> str:
    if similarity >= 0.75:
        return "Excellent"
    elif similarity >= 0.60:
        return "Good"
    elif similarity >= 0.50:
        return "Adequate"
    else:
        return "Poor"


def match_rubric(sections: dict, rubric: dict) -> dict:
    results = {}

    for criterion in rubric["criteria"]:
        criterion_name = criterion["name"]
        criterion_desc = criterion["description"]
        expected_section = criterion.get("expected_section", "")

        section_text = sections.get(expected_section, "")

        if not section_text.strip():
            results[criterion_name] = {
                "matched_section": expected_section,
                "similarity_score": 0.0,
                "compliance_level": "Missing Section"
            }
            continue

        criterion_embedding = model.encode(criterion_desc, convert_to_tensor=True)
        section_embedding = model.encode(section_text[:1500], convert_to_tensor=True)

        similarity = util.cos_sim(criterion_embedding, section_embedding).item()
        similarity = round(similarity, 4)

        results[criterion_name] = {
            "matched_section": expected_section,
            "similarity_score": similarity,
            "compliance_level": score_band(similarity)
        }

    return results