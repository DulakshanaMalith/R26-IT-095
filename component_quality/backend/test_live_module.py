import os
import sys
sys.path.append(os.path.abspath("."))
from src.core.resource_recommender import recommend_resources

def run_test(name, missing_sections, weakness, feedback):
    print(f"\n--- {name} ---")
    res = recommend_resources(weakness, feedback, missing_sections=missing_sections, top_k=3)
    for i, r in enumerate(res):
        print(f"{i+1}. {r['category']} - {r['title']}")

run_test("Test 1: Abstract, Intro, Lit Review", ["Abstract", "Introduction", "Literature Review"], "weak methodology and data collection", "")
run_test("Test 2: Abstract only", ["Abstract"], "weak methodology and data collection", "")
run_test("Test 3: No missing sections", [], "weak methodology and data collection", "")
run_test("Test 4: Methodology, Expected Outcomes", ["Methodology", "Expected Outcomes"], "weak structure and abstract", "")

