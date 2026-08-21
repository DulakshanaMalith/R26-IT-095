import os
import sys
sys.path.append(os.path.abspath("."))
from src.core.resource_recommender import recommend_resources

print("TEST LIVE DIAG")
res = recommend_resources(
    weakness_text="The proposal is weak.",
    feedback_text="Needs better structure.",
    missing_sections=["Abstract", "Introduction", "Literature Review"],
    top_k=3
)
for r in res:
    print(r['title'], "->", r['category'], r['url'])
