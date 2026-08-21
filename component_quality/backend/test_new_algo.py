import json
import re

def normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

RESOURCE_LIBRARY = {
    "Abstract": [{"title": "Abstract Res", "url": "http://example.com/abs", "keywords": ["abstract", "summary"]}],
    "Introduction": [{"title": "Intro Res", "url": "http://example.com/intro", "keywords": ["introduction", "background"]}],
    "Literature Review": [{"title": "Lit Review Res", "url": "http://example.com/lit", "keywords": ["literature review", "related work"]}],
    "Methodology": [{"title": "Methods Res", "url": "http://example.com/meth", "keywords": ["methodology", "methods"]}],
    "Data Collection": [{"title": "Data Coll Res", "url": "http://example.com/data", "keywords": ["data collection"]}],
    "Expected Outcomes": [{"title": "Outcomes Res", "url": "http://example.com/out", "keywords": ["expected outcomes"]}],
    "Structure": [{"title": "Structure Res", "url": "http://example.com/struct", "keywords": ["structure", "paragraph"]}],
    "Problem Statement": [{"title": "Problem Res", "url": "http://example.com/prob", "keywords": ["problem statement", "research gap"]}]
}

MISSING_SECTION_MAPPING = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "literature review": "Literature Review",
    "related work": "Literature Review",
    "methodology": "Methodology",
    "research gap": "Problem Statement",
    "problem statement": "Problem Statement",
    "expected outcomes": "Expected Outcomes",
}

def score_resource(combined_text: str, keywords: list[str]):
    text_tokens = set(combined_text.split())
    matched_keywords = []
    score = 0
    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if " " in normalized_keyword:
            if normalized_keyword in combined_text:
                matched_keywords.append(keyword)
                score += 2
        elif normalized_keyword in text_tokens:
            matched_keywords.append(keyword)
            score += 1
    return score, matched_keywords

def is_valid_resource_url(url): return True

def recommend_resources(
    weakness_text: str,
    feedback_text: str = "",
    missing_sections: list[str] = None,
    top_k: int = 3,
):
    combined_text = normalize_text(f"{weakness_text} {feedback_text}")
    all_scored = []
    
    for category, resources in RESOURCE_LIBRARY.items():
        for resource in resources:
            url = str(resource.get("url", "")).strip()
            if not is_valid_resource_url(url): continue
            score, matched_keywords = score_resource(combined_text, resource["keywords"])
            all_scored.append({
                "category": category,
                "title": resource["title"],
                "url": url,
                "score": score,
                "matched_keywords": matched_keywords,
            })
            
    missing_categories = []
    if missing_sections:
        for section in missing_sections:
            sec_lower = section.lower()
            mapped = MISSING_SECTION_MAPPING.get(sec_lower)
            if mapped and mapped not in missing_categories:
                missing_categories.append(mapped)
                
    final_recommendations = []
    used_categories = set()
    
    for category in missing_categories:
        cat_resources = [r for r in all_scored if r["category"] == category]
        if cat_resources:
            cat_resources.sort(key=lambda r: -r["score"])
            best = dict(cat_resources[0])
            best["matched_keywords"] = best["matched_keywords"] + [f"Missing Section: {category}"]
            final_recommendations.append(best)
            used_categories.add(category)
            
    if len(final_recommendations) < top_k:
        generic_pool = [r for r in all_scored if r["category"] not in used_categories]
        generic_pool.sort(
            key=lambda item: (
                -item["score"],
                item["category"] not in {"Academic Writing", "Structure"},
                item["category"],
            )
        )
        needed = top_k - len(final_recommendations)
        final_recommendations.extend(generic_pool[:needed])
        
    return final_recommendations[:top_k]

# Run tests
def run_test(name, missing_sections, weakness, feedback):
    print(f"\n--- {name} ---")
    res = recommend_resources(weakness, feedback, missing_sections=missing_sections, top_k=3)
    for i, r in enumerate(res):
        print(f"{i+1}. {r['category']} - {r['title']}")

run_test("Test 1: Abstract, Intro, Lit Review", ["Abstract", "Introduction", "Literature Review"], "weak methodology and data collection", "")
run_test("Test 2: Abstract only", ["Abstract"], "weak methodology and data collection", "")
run_test("Test 3: No missing sections", [], "weak methodology and data collection", "")
run_test("Test 4: Methodology, Expected Outcomes", ["Methodology", "Expected Outcomes"], "weak structure and abstract", "")

