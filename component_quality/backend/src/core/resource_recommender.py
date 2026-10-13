"""Recommend academic-writing resources from detected weaknesses and feedback."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import os
import concurrent.futures

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

ROOT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = ROOT_DIR / "results"
DEMO_PATH = RESULTS_DIR / "resource_recommendation_demo.txt"


def get_tavily_client() -> Any:
    api_key = os.getenv("TAVILY_API_KEY")
    is_enabled = os.getenv("TAVILY_ENABLED", "false").lower() == "true"
    if is_enabled and api_key and TavilyClient:
        try:
            return TavilyClient(api_key=api_key)
        except Exception:
            return None
    return None


def fetch_tavily_for_need(client: Any, need: dict[str, Any]) -> list[dict[str, Any]]:
    area = need.get("area", "")
    status = need.get("status", "missing")
    if status == "insufficient":
        query = f"how to improve a short research proposal {area} academic writing guide"
    else:
        query = f"how to write a strong research proposal {area} academic writing guide"
    try:
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=2,
            include_domains=["edu", "ac.uk", "writingcenter"]
        )
        results = []
        for res in response.get("results", []):
            sec_lower = area.lower().replace("_", " ")
            category = MISSING_SECTION_MAPPING.get(sec_lower, area)
            results.append({
                "category": category,
                "area": category,
                "status": need.get("status", "insufficient"),
                "reason": need.get("reason", ""),
                "title": res.get("title", "External Resource"),
                "description": res.get("content", "")[:200] + "...",
                "url": res.get("url", ""),
                "source": "Tavily Web Search",
                "resource_type": "Academic Guide",
                "provider": "tavily",
                "score": res.get("score", 0.9),
                "keyword_score": 0,
                "matched_keywords": []
            })
        return results
    except Exception as e:
        print(f"Tavily search failed for query '{query}': {e}")
        return []


def is_valid_resource_url(value: Any) -> bool:
    """Return True only for non-empty HTTP(S) resource links."""
    if not value:
        return False

    try:
        parsed = urlparse(str(value).strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


RESOURCE_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "Abstract": [
        {
            "title": "Writing an Effective Research Abstract",
            "description": "Guidance on summarizing the research problem, objectives, methodology, results/expected outcomes, and contribution in a concise academic abstract.",
            "url": "https://writingcenter.gmu.edu/writing-resources/research-based-writing",
            "keywords": [
                "abstract",
                "summary",
                "overview",
                "concise",
                "summarize",
            ],
        }
    ],
    "Research Question": [
        {
            "title": "Developing a Focused Research Question",
            "description": "Guidance for making research questions clear, specific, feasible, and answerable.",
            "url": "https://writingcenter.gmu.edu/writing-resources/research-based-writing/how-to-write-a-research-question",
            "keywords": [
                "research question",
                "research questions",
                "rq",
                "scope",
                "broad",
                "specific",
                "answerable",
                "focus",
            ],
        }
    ],
    "Objectives": [
        {
            "title": "Writing Measurable Research Objectives",
            "description": "A practical guide to aligning concrete objectives with the research problem and questions.",
            "url": "https://sites.gsu.edu/rcb-writing/research-objectives/",
            "keywords": [
                "objective",
                "objectives",
                "aim",
                "aims",
                "goal",
                "goals",
                "measurable",
                "alignment",
            ],
        }
    ],
    "Literature Review": [
        {
            "title": "Building a Critical Literature Review",
            "description": "Techniques for synthesizing prior research, identifying gaps, and positioning a study.",
            "url": "https://owl.purdue.edu/owl/research_and_citation/conducting_research/writing_a_literature_review.html",
            "keywords": [
                "literature review",
                "related work",
                "state of the art",
                "sota",
                "research gap",
                "prior research",
                "synthesis",
                "sources",
            ],
        }
    ],
    "Methodology": [
        {
            "title": "Designing a Reproducible Methodology",
            "description": "Guidance on research design, sampling, data collection, and transparent procedures.",
            "url": "https://writingcenter.tamu.edu/guides/resources/scientific-writing.html",
            "keywords": [
                "methodology",
                "method",
                "methods",
                "research design",
                "participant",
                "participants",
                "sample",
                "sampling",
                "data collection",
                "procedure",
            ],
        }
    ],
    "Evaluation": [
        {
            "title": "Planning a Sound Research Evaluation",
            "description": "An introduction to evaluation criteria, metrics, baselines, validity, and analysis plans.",
            "url": "https://writingcenter.tamu.edu/guides/resources/scientific-writing.html",
            "keywords": [
                "evaluation",
                "evaluate",
                "metric",
                "metrics",
                "baseline",
                "validity",
                "analysis",
                "experiment",
                "measurement",
            ],
        }
    ],
    "Academic Writing": [
        {
            "title": "Improving Academic Clarity and Style",
            "description": "Strategies for concise sentences, precise vocabulary, transitions, and formal academic tone.",
            "url": "https://owl.purdue.edu/owl/general_writing/academic_writing/index.html",
            "keywords": [
                "academic writing",
                "language",
                "grammar",
                "clarity",
                "unclear",
                "sentence",
                "wording",
                "tone",
                "readability",
                "concise",
            ],
        }
    ],
    "Structure": [
        {
            "title": "Structuring a Coherent Research Proposal",
            "description": "Guidance on logical sections, paragraph flow, signposting, and a consistent argument.",
            "url": "https://owl.purdue.edu/owl/general_writing/academic_writing/paragraphs_and_paragraphing/index.html",
            "keywords": [
                "structure",
                "organization",
                "organisation",
                "paragraph",
                "section",
                "flow",
                "coherence",
                "transition",
                "common thread",
                "order",
            ],
        }
    ],
    "Referencing": [
        {
            "title": "Citing and Referencing Academic Sources",
            "description": "A guide to supporting claims, formatting citations, and maintaining a consistent bibliography.",
            "url": "https://owl.purdue.edu/owl/research_and_citation/resources.html",
            "keywords": [
                "reference",
                "references",
                "citation",
                "citations",
                "cite",
                "source",
                "sources",
                "bibliography",
                "unsupported claim",
                "doi",
            ],
        }
    ],
    "Data Collection": [
        {
            "title": "Selecting Data Collection Methods",
            "description": "Research material for choosing and explaining suitable data collection methods.",
            "url": "https://writingcenter.tamu.edu/guides/resources/scientific-writing.html",
            "keywords": [
                "data collection",
                "collect data",
                "survey",
                "interview",
                "observation",
                "questionnaire",
                "instrument",
                "participants",
                "dataset",
            ],
        }
    ],
    "Research Gap": [
        {
            "title": "Identifying a Research Gap",
            "description": "Guidance on identifying and explaining gaps in existing research.",
            "url": "https://writingcenter.gmu.edu/writing-resources/research-based-writing/writing-a-literature-review",
            "keywords": [
                "research gap",
                "gap",
                "missing",
                "underexplored",
                "limited studies",
                "prior work",
                "literature gap",
            ],
        }
    ],
    "Problem Statement": [
        {
            "title": "Writing a Research Problem Statement",
            "description": "Guidance on defining a clear, researchable problem statement in a proposal.",
            "url": "https://writingcenter.tamu.edu/guides/resources/proposals.html",
            "keywords": [
                "problem statement",
                "research problem",
                "problem",
                "motivation",
                "issue",
                "context",
                "rationale",
            ],
        }
    ],
    "Innovation": [
        {
            "title": "Clarifying Research Innovation and Contribution",
            "description": "Guidance on explaining significance, contribution, and innovation in a research proposal.",
            "url": "https://writingcenter.tamu.edu/guides/resources/proposals.html",
            "keywords": [
                "innovation",
                "novelty",
                "contribution",
                "original",
                "new approach",
                "significance",
                "impact",
            ],
        }
    ],
    "Introduction": [
        {
            "title": "Writing a Strong Introduction",
            "description": "Guidance on setting the context, stating the problem, and forecasting the proposal structure.",
            "url": "https://owl.purdue.edu/owl/general_writing/academic_writing/paragraphs_and_paragraphing/index.html",
            "keywords": [
                "introduction",
                "background",
                "context",
                "opening",
            ],
        }
    ],
    "Expected Outcomes": [
        {
            "title": "Defining Expected Outcomes",
            "description": "Guidance on articulating the expected results, deliverables, and impact of the research.",
            "url": "https://writingcenter.tamu.edu/guides/resources/proposals.html",
            "keywords": [
                "expected outcomes",
                "results",
                "deliverables",
                "impact",
            ],
        }
    ],
    "Timeline": [
        {
            "title": "Planning a Research Timeline",
            "description": "Guidance on structuring a realistic timeline, milestones, and work breakdown.",
            "url": "https://writingcenter.tamu.edu/guides/resources/proposals.html",
            "keywords": [
                "timeline",
                "gantt",
                "schedule",
                "milestones",
                "plan",
            ],
        }
    ],
    "Ethics": [
        {
            "title": "Addressing Research Ethics",
            "description": "Guidance on ethical considerations, consent, privacy, and responsible conduct of research.",
            "url": "https://writingcenter.tamu.edu/guides/resources/scientific-writing.html",
            "keywords": [
                "ethics",
                "ethical",
                "privacy",
                "consent",
            ],
        }
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for case-insensitive keyword and phrase matching."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def score_resource(combined_text: str, keywords: list[str]) -> tuple[int, list[str]]:
    """Score one resource using exact token and multi-word phrase overlap."""
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


MISSING_SECTION_MAPPING = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "research gap": "Research Gap",
    "problem statement": "Problem Statement",
    "research problem": "Problem Statement",
    "objectives": "Objectives",
    "aims": "Objectives",
    "literature review": "Literature Review",
    "related work": "Literature Review",
    "methodology": "Methodology",
    "data collection": "Data Collection",
    "evaluation": "Evaluation",
    "validation": "Evaluation",
    "expected outcomes": "Expected Outcomes",
    "results": "Expected Outcomes",
    "limitations": "Evaluation",
    "timeline": "Timeline",
    "gantt": "Timeline",
    "ethics": "Ethics",
    "conclusion": "Structure",
}

def recommend_resources(
    weakness_text: str,
    feedback_text: str = "",
    missing_sections: list[str] | None = None,
    learning_needs: list[dict[str, Any]] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Return the highest-ranked resources for weakness, feedback text, and missing structural sections."""
    if not isinstance(weakness_text, str) or not weakness_text.strip():
        raise ValueError("weakness_text must be a non-empty string.")
    if not isinstance(feedback_text, str):
        raise TypeError("feedback_text must be a string.")
    if not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")

    final_recommendations = []
    
    # Process explicit learning_needs
    needs_to_process = learning_needs or []
    if missing_sections and not learning_needs:
        for section in missing_sections:
            needs_to_process.append({"area": section, "status": "missing", "reason": f"Missing {section} section"})

    # Prioritize top_k needs
    needs_to_process = needs_to_process[:top_k]

    tavily_client = get_tavily_client()
    if tavily_client and needs_to_process:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_need = {
                executor.submit(fetch_tavily_for_need, tavily_client, need): need
                for need in needs_to_process
            }
            for future in concurrent.futures.as_completed(future_to_need):
                results = future.result()
                if results:
                    final_recommendations.append(results[0])

    if len(final_recommendations) >= top_k:
        return final_recommendations[:top_k]

    # Fallback to local RESOURCE_LIBRARY
    combined_text = normalize_text(f"{weakness_text} {feedback_text}")
    all_scored = []

    for category, resources in RESOURCE_LIBRARY.items():
        for resource in resources:
            url = str(resource.get("url", "")).strip()
            if not is_valid_resource_url(url):
                continue
            score, matched_keywords = score_resource(
                combined_text,
                resource["keywords"],
            )
            all_scored.append(
                {
                    "category": category,
                    "area": category,
                    "status": "",
                    "reason": "",
                    "title": resource["title"],
                    "description": resource["description"],
                    "url": url,
                    "source": "Local Library",
                    "resource_type": "Academic Guide",
                    "provider": "local",
                    "score": score,
                    "keyword_score": score,
                    "matched_keywords": matched_keywords,
                }
            )

    missing_categories = []
    for need in needs_to_process:
        sec_lower = need.get("area", "").lower().replace("_", " ")
        mapped = MISSING_SECTION_MAPPING.get(sec_lower)
        if mapped and mapped not in missing_categories:
            missing_categories.append(mapped)

    used_categories = {r.get("category") for r in final_recommendations}

    if needs_to_process:
        # Fulfill structural needs strictly without padding with generic resources
        for category in missing_categories:
            if category in used_categories:
                continue
            cat_resources = [r for r in all_scored if r["category"] == category]
            if cat_resources:
                cat_resources.sort(key=lambda r: -r["score"])
                best = dict(cat_resources[0])
                best["matched_keywords"] = best["matched_keywords"] + [f"Missing Section: {category}"]
                matching_need = next((n for n in needs_to_process if MISSING_SECTION_MAPPING.get(n.get("area", "").lower().replace("_", " ")) == category), None)
                if matching_need:
                    best["status"] = matching_need.get("status", "missing")
                    best["reason"] = matching_need.get("reason", "")
                    best["area"] = matching_need.get("area", category)
                final_recommendations.append(best)
                used_categories.add(category)
    else:
        # Preserve generic weakness semantic recommendation behavior if no needs provided
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

    # Deduplicate URLs while preserving multiple areas
    deduped = []
    seen_urls = set()
    for rec in final_recommendations:
        url = rec.get("url", "")
        if url in seen_urls:
            # Optionally merge reasons or matched_keywords here
            continue
        seen_urls.add(url)
        deduped.append(rec)

    return deduped[:top_k]


def format_recommendations(
    weakness_text: str,
    feedback_text: str,
    recommendations: list[dict[str, Any]],
) -> str:
    """Format one recommendation example for terminal and file output."""
    lines = [
        f"Weakness: {weakness_text}",
        f"Feedback: {feedback_text or '(none)'}",
        "-" * 80,
    ]
    for rank, resource in enumerate(recommendations, start=1):
        matched = ", ".join(resource["matched_keywords"]) or "fallback"
        lines.extend(
            [
                f"Recommendation {rank}",
                f"Category: {resource['category']}",
                f"Title: {resource['title']}",
                f"Description: {resource['description']}",
                f"URL: {resource['url']}",
                f"Keyword score: {resource['score']}",
                f"Matched keywords: {matched}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def main() -> None:
    """Run sample cases and save the recommendation demonstration."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    sample_cases = [
        (
            "The research question is too broad and lacks a clear scope.",
            "Narrow the question so it is specific and answerable.",
        ),
        (
            "The participant selection and data collection method are unclear.",
            "Explain the sampling procedure and research design.",
        ),
        (
            "This claim has no supporting source.",
            "Add an appropriate citation and check the bibliography.",
        ),
        (
            "The paragraph is difficult to follow and contains unclear wording.",
            "Improve sentence clarity and add transitions between ideas.",
        ),
        (
            "The evaluation does not define metrics or a baseline.",
            "Describe how validity and performance will be measured.",
        ),
    ]

    demo_sections = []
    for weakness_text, feedback_text in sample_cases:
        recommendations = recommend_resources(
            weakness_text,
            feedback_text,
            missing_sections=[],
            top_k=3,
        )
        section = format_recommendations(
            weakness_text,
            feedback_text,
            recommendations,
        )
        demo_sections.append(section)
        print("\n" + section)

    DEMO_PATH.write_text("\n\n".join(demo_sections) + "\n", encoding="utf-8")
    print(f"\nRecommendation demo saved to: {DEMO_PATH}")


if __name__ == "__main__":
    main()
