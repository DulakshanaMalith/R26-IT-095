from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import Response
from src.api.schemas import *
from src.api.services.core_logic import *

router = APIRouter()

@router.get("/grading-analytics")
def get_grading_analytics() -> dict[str, Any]:
    """Aggregate real semantic grading history for supervisor analytics."""
    history = load_grading_history()
    analysis_index = build_analysis_history_index()
    scores = [
        max(0.0, min(float(GRADING_MAX_SCORE), float(record.get("predicted_score"))))
        for record in history
        if isinstance(record, dict) and record.get("predicted_score") is not None
    ]
    percentages = [
        round(
            max(
                0.0,
                min(
                    100.0,
                    float(record.get("percentage_score", percentage_from_score(float(record.get("predicted_score", 0))))),
                ),
            ),
            1,
        )
        for record in history
        if isinstance(record, dict) and record.get("predicted_score") is not None
    ]
    distribution = {
        "Very Strong": 0,
        "Strong": 0,
        "Moderate": 0,
        "Developing": 0,
        "Limited Semantic Evidence": 0,
    }
    readiness_distribution = {
        "Ready for Supervisor Review": 0,
        "Minor Revision Required": 0,
        "Needs Revision": 0,
        "Incomplete Proposal": 0,
        "Not Available": 0,
    }
    completeness_values: list[float] = []
    final_readiness_values: list[float] = []
    final_readiness_distribution = {
        "Excellent": 0,
        "Very Good": 0,
        "Good": 0,
        "Satisfactory": 0,
        "Minor Revision Required": 0,
        "Major Revision Required": 0,
        "Needs Major Revision": 0,
        "Incomplete Proposal": 0,
    }
    missing_section_counter: Counter[str] = Counter()
    daily_scores: dict[str, list[float]] = {}
    daily_percentages: dict[str, list[float]] = {}
    daily_completeness: dict[str, list[float]] = {}
    daily_final_readiness: dict[str, list[float]] = {}

    for record in history:
        if not isinstance(record, dict):
            continue
        score = record.get("predicted_score")
        percentage = max(0.0, min(100.0, float(record.get("percentage_score", percentage_from_score(float(score or 0))))))
        label = score_label(percentage)
        if label in distribution:
            distribution[label] += 1
        completeness_payload = normalize_completeness_payload(
            record.get("proposal_completeness"),
            linked_analysis_text_for_grading(record, analysis_index),
        )
        readiness_payload = record.get("submission_readiness")
        if isinstance(completeness_payload, dict) and completeness_payload.get("percentage") is not None:
            completeness_value = max(0.0, min(100.0, float(completeness_payload.get("percentage"))))
            completeness_values.append(completeness_value)
            for section in completeness_payload.get("missing_sections") or []:
                missing_section_counter[str(section)] += 1
        final_readiness = normalize_final_readiness_payload(record, round(percentage, 1), completeness_payload)
        if isinstance(final_readiness, dict) and final_readiness.get("percentage") is not None:
            final_value = max(0.0, min(100.0, float(final_readiness["percentage"])))
            final_readiness_values.append(final_value)
            final_label = str(final_readiness.get("label") or final_readiness_label(final_value))
            final_readiness_distribution.setdefault(final_label, 0)
            final_readiness_distribution[final_label] += 1
        if isinstance(completeness_payload, dict) and completeness_payload.get("percentage") is not None:
            status_value = readiness_for_completeness(float(completeness_payload["percentage"])).status
            readiness_distribution.setdefault(str(status_value), 0)
            readiness_distribution[str(status_value)] += 1
        else:
            readiness_distribution["Not Available"] += 1
        timestamp = str(record.get("timestamp") or "")
        if timestamp and score is not None:
            daily_scores.setdefault(timestamp[:10], []).append(float(score))
            daily_percentages.setdefault(timestamp[:10], []).append(percentage)
            if isinstance(completeness_payload, dict) and completeness_payload.get("percentage") is not None:
                daily_completeness.setdefault(timestamp[:10], []).append(float(completeness_payload["percentage"]))
            if isinstance(final_readiness, dict) and final_readiness.get("percentage") is not None:
                daily_final_readiness.setdefault(timestamp[:10], []).append(float(final_readiness["percentage"]))

    score_trend = [
        {
            "date": date,
            "average_score": round(sum(values) / len(values), 2),
            "average_percentage": round(
                sum(daily_percentages.get(date, [])) / len(daily_percentages.get(date, []) or [1]),
                1,
            ),
            "average_completeness": round(
                sum(daily_completeness.get(date, [])) / len(daily_completeness.get(date, []) or [1]),
                1,
            ) if daily_completeness.get(date) else None,
            "average_final_readiness": round(
                sum(daily_final_readiness.get(date, [])) / len(daily_final_readiness.get(date, []) or [1]),
                1,
            ) if daily_final_readiness.get(date) else None,
        }
        for date, values in sorted(daily_scores.items())
        if values
    ]
    recent_grades = []
    for record in list(reversed(history))[:10]:
        if not isinstance(record, dict):
            continue
        score = max(0.0, min(float(GRADING_MAX_SCORE), float(record.get("predicted_score", 0))))
        percentage = max(0.0, min(100.0, float(record.get("percentage_score", percentage_from_score(score)))))
        completeness_payload = normalize_completeness_payload(
            record.get("proposal_completeness"),
            linked_analysis_text_for_grading(record, analysis_index),
        )
        readiness_payload = record.get("submission_readiness")
        if completeness_payload:
            readiness_payload = readiness_for_completeness(float(completeness_payload.get("percentage", 0))).model_dump()
        else:
            readiness_payload = None
        final_readiness = normalize_final_readiness_payload(record, round(percentage, 1), completeness_payload)
        semantic_label = score_label(percentage)
        final_assessment = normalize_final_proposal_assessment_semantic_label(
            record.get("final_proposal_assessment"),
            round(percentage, 1),
            semantic_label,
        )
        recent_grades.append(
            {
                **record,
                "predicted_score": round(score, 2),
                "max_score": int(record.get("max_score", GRADING_MAX_SCORE)),
                "percentage_score": round(percentage, 1),
                "semantic_percentage": round(percentage, 1),
                "semantic_label": semantic_label,
                "score_label": semantic_label,
                "model_status": record.get("model_status", "baseline"),
                "proposal_completeness": completeness_payload,
                "completeness_percentage": completeness_payload.get("percentage") if completeness_payload else None,
                "final_readiness": final_readiness,
                "final_readiness_percentage": final_readiness.get("percentage") if isinstance(final_readiness, dict) else None,
                "final_readiness_label": final_readiness.get("label") if isinstance(final_readiness, dict) else None,
                "missing_sections": completeness_payload.get("missing_sections", []) if completeness_payload else [],
                "submission_readiness": readiness_payload,
                "submission_status": readiness_payload.get("status") if isinstance(readiness_payload, dict) else "Not Available",
                "submission_reason": readiness_payload.get("reason") if isinstance(readiness_payload, dict) else legacy_completeness_unavailable_reason(),
                "final_proposal_assessment": final_assessment,
                "warning": record.get("warning", GRADING_WARNING),
            }
        )

    return {
        "total_graded": len(history),
        "average_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "highest_score": round(max(scores), 2) if scores else 0,
        "lowest_score": round(min(scores), 2) if scores else 0,
        "max_score": GRADING_MAX_SCORE,
        "average_percentage": round(sum(percentages) / len(percentages), 1) if percentages else 0,
        "highest_percentage": round(max(percentages), 1) if percentages else 0,
        "lowest_percentage": round(min(percentages), 1) if percentages else 0,
        "score_distribution": distribution,
        "average_proposal_completeness": round(sum(completeness_values) / len(completeness_values), 1) if completeness_values else None,
        "average_final_readiness": round(sum(final_readiness_values) / len(final_readiness_values), 1) if final_readiness_values else None,
        "final_readiness_distribution": final_readiness_distribution,
        "most_missing_section": missing_section_counter.most_common(1)[0][0] if missing_section_counter else None,
        "missing_section_distribution": dict(missing_section_counter),
        "submission_readiness_distribution": readiness_distribution,
        "score_trend": score_trend,
        "daily_average_percentage": [
            {
                "date": item["date"],
                "average_percentage": item["average_percentage"],
            }
            for item in score_trend
        ],
        "daily_average_completeness": [
            {
                "date": item["date"],
                "average_completeness": item["average_completeness"],
            }
            for item in score_trend
            if item.get("average_completeness") is not None
        ],
        "daily_average_final_readiness": [
            {
                "date": item["date"],
                "average_final_readiness": item["average_final_readiness"],
            }
            for item in score_trend
            if item.get("average_final_readiness") is not None
        ],
        "recent_grades": recent_grades,
    }

@router.get(
    "/supervisor-analytics",
    response_model=SupervisorAnalyticsResponse,
    summary="Supervisor analytics from saved proposal analyses",
    description=(
        "Returns real-time supervisor analytics aggregated only from "
        "data/analysis_history.json. No mock data, grading scores, or placeholder "
        "analytics are used."
    ),
)
def get_supervisor_analytics() -> SupervisorAnalyticsResponse:
    """Generate aggregate analytics from real saved analysis history only."""
    history, warning = load_analysis_history_for_analytics()
    logger.info("Loaded %d analysis history records for supervisor analytics.", len(history))

    tag_counter: Counter[str] = Counter()
    tag_distribution = {
        "Weakness": 0,
        "Strength": 0,
        "Other": 0,
        "Highlight": 0,
    }
    resource_counter: Counter[tuple[str, str]] = Counter()
    feedback_count_total = 0
    resource_count_total = 0
    daily_counter: Counter[str] = Counter()

    for record in history:
        if not isinstance(record, dict):
            continue
        record = effective_analysis_record(record)

        tag = record.get("predicted_tag")
        if tag:
            tag_name = str(tag)
            tag_counter[tag_name] += 1
            tag_distribution[tag_name] = tag_distribution.get(tag_name, 0) + 1

        feedback = record.get("retrieved_feedback") or []
        resources = record.get("recommended_resources") or []
        if isinstance(feedback, list):
            feedback_count_total += len(feedback)
        if isinstance(resources, list):
            resource_count_total += len(resources)
            for resource in resources:
                if isinstance(resource, dict):
                    title = str(resource.get("title") or "Untitled resource")
                    category = str(resource.get("category") or "Uncategorized")
                    resource_counter[(title, category)] += 1

        timestamp = str(record.get("timestamp") or "")
        if timestamp:
            daily_counter[timestamp[:10]] += 1

    common_resources = [
        SupervisorCommonResource(title=title, category=category, count=count)
        for (title, category), count in resource_counter.most_common(10)
    ]
    daily_counts = [
        SupervisorDailyCount(date=date, count=count)
        for date, count in sorted(daily_counter.items())
    ]
    recent_analyses = [
        SupervisorRecentAnalysis(
            id=str(record.get("id")) if record.get("id") else None,
            timestamp=str(record.get("timestamp")) if record.get("timestamp") else None,
            source=normalise_source(record.get("source")),
            filename=str(record.get("filename")) if record.get("filename") else None,
            predicted_tag=str(effective_record.get("predicted_tag")) if effective_record.get("predicted_tag") else None,
            model_predicted_tag=str(effective_record.get("model_predicted_tag")) if effective_record.get("model_predicted_tag") else None,
            classification_reason=str(effective_record.get("classification_reason")) if effective_record.get("classification_reason") else None,
            input_preview=str(record.get("input_preview") or ""),
        )
        for record in reversed(history)
        if isinstance(record, dict)
        for effective_record in [effective_analysis_record(record)]
    ][:10]
    most_common_tag = tag_counter.most_common(1)[0][0] if tag_counter else None

    response = SupervisorAnalyticsResponse(
        total_analyses=len(history),
        tag_distribution=tag_distribution,
        most_common_tag=most_common_tag,
        feedback_count_total=feedback_count_total,
        resource_count_total=resource_count_total,
        common_resources=common_resources,
        daily_counts=daily_counts,
        daily_review_count=daily_counts,
        recent_analyses=recent_analyses,
        warning=warning,
    )
    logger.info("Supervisor analytics generated successfully.")
    return response