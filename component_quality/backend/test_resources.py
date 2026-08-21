import os
import sys
from pprint import pprint
sys.path.append(os.path.abspath("."))
from src.core.resource_recommender import recommend_resources

res_with_missing = recommend_resources(
    weakness_text="The proposal is weak.",
    feedback_text="Needs better structure.",
    missing_sections=["Abstract", "Methodology"],
    top_k=3
)
print("=== With missing_sections ===")
for r in res_with_missing:
    print(r['title'], "->", r['category'])

res_without = recommend_resources(
    weakness_text="The proposal is weak.",
    feedback_text="Needs better structure.",
    missing_sections=[],
    top_k=3
)
print("\n=== Without missing_sections ===")
for r in res_without:
    print(r['title'], "->", r['category'])
