from datetime import datetime
from typing import Any, Dict, List


def _priority_from_score(score: float) -> str:
    if score < 40:
        return "High Priority"
    if score < 60:
        return "Medium Priority"
    return "Low Priority"


def _section_explanation(name: str, score: float) -> str:
    n = name.lower()
    if "literature" in n:
        return (
            "The literature review demonstrates limited critical synthesis of prior work. "
            "Comparative analysis between studies is not sufficiently developed."
            if score < 60
            else "The literature review shows reasonable synthesis, with scope to improve critical contrast across sources."
        )
    if "method" in n:
        return (
            "The methodology lacks clarity in research design justification, variable definition, or procedural rigor."
            if score < 60
            else "The methodology is generally clear and coherent, with room for stronger validation rationale."
        )
    if "reference" in n or "writing" in n:
        return (
            "Academic tone and citation consistency require improvement for scholarly credibility."
            if score < 60
            else "Academic writing quality is acceptable, with minor refinements needed in referencing consistency."
        )
    return (
        "This section requires clearer argumentation, evidence alignment, and rubric-focused completeness."
        if score < 60
        else "This section aligns reasonably with rubric expectations, with moderate enhancement opportunities."
    )


def _section_improvement(name: str) -> str:
    n = name.lower()
    if "literature" in n:
        return "Compare at least 3–5 key studies directly, identify methodological differences, and synthesize trends."
    if "method" in n:
        return "Specify research design choices, sampling logic, implementation steps, and evaluation strategy."
    if "reference" in n or "writing" in n:
        return "Standardize citation format and revise language for formal academic clarity."
    return "Strengthen structure, deepen evidence, and map content explicitly to rubric criteria."


def _group_resources(recommendations: Dict[str, Any]) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for criterion, items in (recommendations or {}).items():
        bucket = {"guides": [], "videos": [], "articles": []}
        for item in (items or []):
            if isinstance(item, str):
                bucket["guides"].append({"title": item, "url": ""})
                continue
            typ = str(item.get("type", "")).lower()
            row = {"title": item.get("title") or item.get("name") or "Resource", "url": item.get("url", "")}
            if "youtube" in typ or "video" in typ:
                bucket["videos"].append(row)
            elif "article" in typ or "paper" in typ or "link" in typ:
                bucket["articles"].append(row)
            else:
                bucket["guides"].append(row)
        grouped[criterion] = bucket
    return grouped


def generate_report_payload(
    rubric_results: dict,
    weaknesses: list,
    recommendations: dict,
    score_summary: dict,
    ml_result: dict,
    hybrid_result: dict,
    scoring_policy: dict | None = None,
    student_id: str = "N/A",
    version: str = "Version 1",
) -> dict:
    section_scores = score_summary.get("section_scores", [])

    section_evaluation = []
    for item in section_scores:
        name = item.get("criterion") or item.get("name") or "Unnamed Section"
        raw = float(item.get("raw_score", item.get("raw", 0)))
        weighted = float(item.get("weighted_score", item.get("weighted", 0)))
        section_evaluation.append(
            {
                "criterion": name,
                "raw_score": round(raw, 2),
                "weighted_score": round(weighted, 2),
                "explanation": _section_explanation(name, raw),
                "improvement": _section_improvement(name),
            }
        )

    prioritized = sorted(
        [
            {
                "criterion": w.get("criterion", "Unknown"),
                "issue": w.get("issue", "Weak alignment detected."),
                "score": round(float(w.get("score", 0)) * 100, 2) if float(w.get("score", 0)) <= 1 else round(float(w.get("score", 0)), 2),
                "priority": _priority_from_score(
                    float(w.get("score", 0)) * 100 if float(w.get("score", 0)) <= 1 else float(w.get("score", 0))
                ),
                "impact": "This weakness can reduce overall academic coherence, grading confidence, and supervisor acceptance.",
            }
            for w in (weaknesses or [])
        ],
        key=lambda x: {"High Priority": 0, "Medium Priority": 1, "Low Priority": 2}[x["priority"]],
    )

    final_score = hybrid_result.get("final_score", 0)
    policy = scoring_policy or {}
    semantic_weight = policy.get("semantic_weight")
    ml_weight = policy.get("ml_weight")
    ml_cap = policy.get("ml_score_cap")

    weighting_line = ""
    if semantic_weight is not None and ml_weight is not None:
        weighting_line = (
            f" The final score prioritizes rubric-semantic evidence ({semantic_weight:.2f}) "
            f"over ML estimation ({ml_weight:.2f}) to preserve academic interpretability."
        )

    cap_line = ""
    if ml_cap is not None:
        cap_line = f" ML contribution is capped at {ml_cap:.0f}/100 to avoid over-optimistic inflation."

    executive_summary = (
        f"The manuscript demonstrates an overall performance level reflected by a hybrid score of {final_score}/100 "
        f"({hybrid_result.get('grade', 'N/A')}, {hybrid_result.get('status', 'N/A')}). "
        "Strengths are visible in selected rubric areas; however, several sections require deeper academic synthesis, "
        "clearer methodological justification, and stronger scholarly writing consistency to reach higher-quality research standards."
        f"{weighting_line}{cap_line}"
    )

    return {
        "header": {
            "system_name": "Adaptive Mentorship System",
            "student_id": student_id,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "version": version,
        },
        "executive_summary": executive_summary,
        "score_dashboard": {
            "semantic_score": score_summary.get("overall_score", 0),
            "ml_score": ml_result.get("normalized_ml_score", 0),
            "final_score": hybrid_result.get("final_score", 0),
            "grade": hybrid_result.get("grade", "N/A"),
            "status": hybrid_result.get("status", "N/A"),
        },
        "section_evaluation": section_evaluation,
        "weakness_analysis": prioritized,
        "recommended_resources": _group_resources(recommendations),
        "mentorship_insights": [
            "Prioritize high-impact sections first (literature synthesis and methodological rigor).",
            "Re-check rubric alignment after each revision cycle.",
            "Use scholarly citation consistency and concise academic tone across all sections.",
        ],
        "improvement_plan": [
            {"week": "Week 1", "action": "Revise literature review with comparative synthesis and gap articulation."},
            {"week": "Week 2", "action": "Refine methodology, rationale, and evaluation criteria."},
            {"week": "Week 3", "action": "Improve writing quality, references, and final rubric compliance check."},
        ],
        "scoring_policy": policy,
    }


def generate_feedback(
    rubric_results: dict,
    weaknesses: list,
    recommendations: dict,
    score_summary: dict,
    ml_result: dict,
    hybrid_result: dict,
    scoring_policy: dict | None = None,
) -> dict:
    report = generate_report_payload(
        rubric_results=rubric_results,
        weaknesses=weaknesses,
        recommendations=recommendations,
        score_summary=score_summary,
        ml_result=ml_result,
        hybrid_result=hybrid_result,
        scoring_policy=scoring_policy,
    )

    lines = []
    h = report["header"]
    s = report["score_dashboard"]

    lines.append("Adaptive Mentorship System - Academic Evaluation Report")
    lines.append("=" * 64)
    lines.append(f"Student ID: {h['student_id']} | Date: {h['date']} | Version: {h['version']}")
    lines.append("")
    lines.append("Executive Summary")
    lines.append("-" * 64)
    lines.append(report["executive_summary"])
    lines.append("")
    lines.append("Score Dashboard")
    lines.append("-" * 64)
    lines.append(f"Semantic: {s['semantic_score']} | ML: {s['ml_score']} | Final: {s['final_score']} ({s['grade']}, {s['status']})")

    lines.append("\nSection-wise Scores:")
    for item in score_summary["section_scores"]:
        lines.append(
            f"- {item['criterion']}: "
            f"similarity={item['similarity_score']:.4f}, "
            f"raw score={item['raw_score']}, "
            f"weighted={item['weighted_score']}, "
            f"compliance={item['compliance_level']}"
        )

    lines.append("\nSection-wise Evaluation")
    lines.append("-" * 64)
    for sec in report["section_evaluation"]:
        lines.append(f"* {sec['criterion']} | Raw: {sec['raw_score']} | Weighted: {sec['weighted_score']}")
        lines.append(f"  - Analysis: {sec['explanation']}")
        lines.append(f"  - Improve: {sec['improvement']}")

    lines.append("\nWeakness Analysis (Prioritized)")
    lines.append("-" * 64)
    for w in report["weakness_analysis"]:
        lines.append(f"* [{w['priority']}] {w['criterion']} (Score: {w['score']})")
        lines.append(f"  - Issue: {w['issue']}")
        lines.append(f"  - Impact: {w['impact']}")

    lines.append("\nRecommended Next Steps")
    lines.append("-" * 64)
    for step in report["improvement_plan"]:
        lines.append(f"* {step['week']}: {step['action']}")

    feedback_text = "\n".join(lines)

    # Keep the detailed report structure for PDF generation while exposing
    # normalized keys expected by downstream consumers.
    return {
        "text": feedback_text,
        "header": report.get("header", {}),
        "scores": {
            "overall": score_summary.get("overall_score", 0),
            "section_scores": score_summary.get("section_scores", []),
            "score_dashboard": report.get("score_dashboard", {}),
        },
        "ml_score": ml_result,
        "final_score": hybrid_result,
        "executive_summary": report.get("executive_summary", ""),
        "score_dashboard": report.get("score_dashboard", {}),
        "section_evaluation": report.get("section_evaluation", []),
        "weakness_analysis": report.get("weakness_analysis", []),
        "recommended_resources": report.get("recommended_resources", {}),
        "mentorship_insights": report.get("mentorship_insights", []),
        "improvement_plan": report.get("improvement_plan", []),
        "scoring_policy": report.get("scoring_policy", {}),
    }