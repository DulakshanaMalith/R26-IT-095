from src.core.resource_recommender import recommend_resources

cases = [
    ("A", ["Abstract"]),
    ("B", ["Research Gap"]),
    ("C", ["Abstract", "Research Gap"]),
    ("D", []),
]

for label, missing in cases:
    print(f"\n--- CASE {label} --- missing_sections={missing}")
    results = recommend_resources("Weak research", "Need better text.", missing_sections=missing, top_k=3)
    for r in results:
        print(f"Category: {r['category']}, Title: {r['title']}, Score: {r['score']}, Matched: {r['matched_keywords']}")
