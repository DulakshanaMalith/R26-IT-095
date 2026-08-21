import os
import sys
sys.path.append(os.path.abspath("."))
from src.core.resource_recommender import recommend_resources

def run_test(name, missing_sections, weakness, feedback):
    print(f"\n--- {name} ---")
    print(f"[RESOURCE TRACE] missing_sections: {missing_sections}")
    res = recommend_resources(weakness, feedback, missing_sections=missing_sections, top_k=3)
    final_cats = [r['category'] for r in res]
    print(f"[RESOURCE TRACE] final_resources: {final_cats}")
    for i, r in enumerate(res):
        print(f"{i+1}. {r['category']} - {r['title']} ({r['url']})")

run_test("Test 1: Underscore strings like runtime", ["abstract", "introduction", "literature_review"], "weak methodology and data collection", "")
run_test("Test 2: Only literature review", ["literature_review"], "weak methodology and data collection", "")
run_test("Test 3: No missing sections", [], "weak methodology and data collection", "")
