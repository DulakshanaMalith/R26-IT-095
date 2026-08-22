from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bar_chart_multi(
    datasets: List[List[float]],
    labels: List[str],
    series_colors: List[Any],
    width=170 * mm,
    height=70 * mm,
) -> Drawing:
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 34
    chart.y = 24
    chart.height = height - 40
    chart.width = width - 52
    chart.data = datasets
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.dx = -2
    chart.categoryAxis.labels.dy = -2
    chart.categoryAxis.labels.angle = 20
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueStep = 20

    for idx, color in enumerate(series_colors):
        chart.bars[idx].fillColor = color

    drawing.add(chart)
    return drawing


def _pie_chart(
    data: List[float], labels: List[str], palette: List[Any], width=84 * mm, height=64 * mm
) -> Drawing:
    drawing = Drawing(width, height)
    pie = Pie()
    pie.x = 18
    pie.y = 6
    pie.width = 54 * mm
    pie.height = 54 * mm
    pie.data = data
    pie.labels = labels

    for idx, color in enumerate(palette):
        if idx < len(data):
            pie.slices[idx].fillColor = color

    drawing.add(pie)
    return drawing


def _normalize_section_scores(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    section_scores = report.get("section_scores") or []
    if section_scores:
        return section_scores

    section_eval = report.get("section_evaluation") or []
    normalized = []
    for sec in section_eval:
        normalized.append(
            {
                "criterion": sec.get("criterion", "N/A"),
                "similarity_score": sec.get("similarity_score", 0),
                "raw_score": sec.get("raw_score", 0),
                "weighted_score": sec.get("weighted_score", 0),
                "compliance_level": sec.get("compliance_level", "N/A"),
            }
        )
    return normalized


def save_feedback_as_pdf(report: Dict[str, Any], path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Adaptive Mentorship Academic Evaluation Report",
    )

    styles = getSampleStyleSheet()
    
    # Define custom paragraph styles for professional appearance
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["BodyText"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#475569"),
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    
    section_header = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        leading=17,
        textColor=colors.HexColor("#ffffff"),
        spaceBefore=12,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )
    
    h3_style = ParagraphStyle(
        "H3",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    
    body_style = ParagraphStyle(
        "BodyStyled",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        alignment=TA_JUSTIFY,
    )
    
    small_style = ParagraphStyle(
        "SmallStyled",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    story: List[Any] = []

    header = report.get("header", {})
    score = report.get("score_dashboard", {})
    scoring_policy = report.get("scoring_policy", {}) or {}
    model_metrics = report.get("model_metrics", {}) or {}
    section_scores = _normalize_section_scores(report)
    weaknesses = report.get("weakness_analysis", []) or []
    recommendations = report.get("recommended_resources", {}) or {}
    next_steps = report.get("improvement_plan", []) or []

    # ========== COVER PAGE ==========
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph("ADAPTIVE MENTORSHIP SYSTEM", title_style))
    story.append(Paragraph("Academic Evaluation Report", subtitle_style))
    story.append(Spacer(1, 15 * mm))

    # Cover metadata table
    cover_meta = Table(
        [
            ["Student ID", header.get("student_id", "N/A")],
            ["Submission Version", header.get("version", "Version 1")],
            ["Generated Date", header.get("date", "N/A")],
            ["Academic Status", score.get("status", "N/A")],
        ],
        colWidths=[45 * mm, 80 * mm],
    )
    cover_meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(cover_meta)
    story.append(Spacer(1, 20 * mm))

    # Score summary on cover
    cover_scores = Table(
        [
            ["Final Score", "Grade", "Semantic", "ML Prediction"],
            [
                f"{_safe_float(score.get('final_score')):.2f}/100",
                str(score.get("grade", "N/A")),
                f"{_safe_float(score.get('semantic_score')):.2f}",
                f"{_safe_float(score.get('ml_score')):.2f}",
            ],
        ],
        colWidths=[40 * mm, 35 * mm, 40 * mm, 40 * mm],
    )
    cover_scores.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(cover_scores)
    story.append(PageBreak())

    # ========== EXECUTIVE SUMMARY ==========
    story.append(Paragraph("Executive Summary", section_header))
    exec_summary = report.get(
        "executive_summary",
        f"This submission achieved a final hybrid score of {_safe_float(score.get('final_score')):.2f}/100. "
        f"Semantic evaluation: {_safe_float(score.get('semantic_score')):.2f}, "
        f"ML prediction: {_safe_float(score.get('ml_score')):.2f}. "
        f"Current status: {score.get('status', 'Pending')}.",
    )
    story.append(Paragraph(exec_summary, body_style))
    story.append(Spacer(1, 8 * mm))

    # ========== SCORE DASHBOARD ==========
    story.append(Paragraph("Score Dashboard", h3_style))
    score_table = Table(
        [
            ["Semantic Score", "ML Predicted Score", "Final Hybrid Score", "Grade", "Status"],
            [
                f"{_safe_float(score.get('semantic_score')):.2f}",
                f"{_safe_float(score.get('ml_score')):.2f}",
                f"{_safe_float(score.get('final_score')):.2f}",
                str(score.get("grade", "N/A")),
                str(score.get("status", "N/A")),
            ],
        ],
        colWidths=[34 * mm, 34 * mm, 34 * mm, 28 * mm, 28 * mm],
    )
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(score_table)
    if scoring_policy:
        semantic_weight = _safe_float(scoring_policy.get("semantic_weight"), 0.65)
        ml_weight = _safe_float(scoring_policy.get("ml_weight"), 0.35)
        ml_cap = _safe_float(scoring_policy.get("ml_score_cap"), 85)
        policy_note = (
            f"Scoring policy: semantic rubric weight={semantic_weight:.2f}, "
            f"ML weight={ml_weight:.2f}, ML cap={ml_cap:.0f}/100."
        )
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(policy_note, small_style))
    if model_metrics:
        metric_rows = [
            ["Model", str(model_metrics.get("model_type", "XGBoost Regressor"))],
            ["Pipeline", str(model_metrics.get("pipeline_label", "TF-IDF + XGBoost Pipeline"))],
            ["Dataset", str(model_metrics.get("dataset", "ASAP 2.0"))],
            ["MAE", f"{_safe_float(model_metrics.get('mae')):.4f}"],
            ["RMSE", f"{_safe_float(model_metrics.get('rmse')):.4f}"],
            ["R²", f"{_safe_float(model_metrics.get('r2_score')):.4f}"],
            ["Approx Accuracy", f"{_safe_float(model_metrics.get('approx_accuracy')):.2f}%"],
        ]
        metrics_table = Table(metric_rows, colWidths=[42 * mm, 80 * mm])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Model Performance", h3_style))
        story.append(metrics_table)
    story.append(Spacer(1, 10 * mm))

    # ========== SECTION-WISE EVALUATION ==========
    story.append(Paragraph("Section-wise Evaluation", h3_style))
    if section_scores:
        sec_header = [["Criterion", "Similarity", "Raw Score", "Weighted", "Compliance"]]
        sec_rows = []
        for sec in section_scores:
            sec_rows.append(
                [
                    str(sec.get("criterion", "N/A"))[:30],
                    f"{_safe_float(sec.get('similarity_score')):.4f}",
                    f"{_safe_float(sec.get('raw_score')):.2f}",
                    f"{_safe_float(sec.get('weighted_score')):.2f}",
                    str(sec.get("compliance_level", "N/A")),
                ]
            )
        sec_table = Table(sec_header + sec_rows, colWidths=[55 * mm, 24 * mm, 22 * mm, 22 * mm, 28 * mm])
        sec_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(sec_table)
    else:
        story.append(Paragraph("No section-level scores available.", body_style))
    story.append(Spacer(1, 10 * mm))

    # ========== CHARTS ==========
    if section_scores:
        chart_labels = [
            (str(s.get("criterion", "N/A"))[:12] + "...")
            if len(str(s.get("criterion", "N/A"))) > 12
            else str(s.get("criterion", "N/A"))
            for s in section_scores
        ]
        raw_values = [_safe_float(s.get("raw_score")) for s in section_scores]
        weighted_values = [_safe_float(s.get("weighted_score")) for s in section_scores]

        story.append(Paragraph("Section Score Bar Chart", h3_style))
        story.append(
            _bar_chart_multi(
                [raw_values, weighted_values],
                chart_labels,
                [colors.HexColor("#2563eb"), colors.HexColor("#10b981")],
                width=180 * mm,
                height=80 * mm,
            )
        )
        story.append(Spacer(1, 8 * mm))

    # Score comparison chart
    story.append(Paragraph("Score Comparison Chart", h3_style))
    story.append(
        _bar_chart_multi(
            [[_safe_float(score.get("semantic_score")), _safe_float(score.get("ml_score")), _safe_float(score.get("final_score"))]],
            ["Semantic", "ML", "Final"],
            [colors.HexColor("#1d4ed8")],
            width=140 * mm,
            height=70 * mm,
        )
    )
    story.append(Spacer(1, 8 * mm))

    # Compliance distribution pie chart
    good_count = sum(
        1
        for s in section_scores
        if str(s.get("compliance_level", "")).lower() in {"good", "excellent", "strong"}
    )
    adequate_count = sum(1 for s in section_scores if str(s.get("compliance_level", "")).lower() == "adequate")
    poor_count = max(len(section_scores) - good_count - adequate_count, 0)

    story.append(Paragraph("Compliance Distribution", h3_style))
    story.append(
        _pie_chart(
            [good_count, adequate_count, poor_count],
            ["Good/Strong", "Adequate", "Poor/Missing"],
            [colors.HexColor("#10b981"), colors.HexColor("#3b82f6"), colors.HexColor("#f59e0b")],
            width=100 * mm,
            height=80 * mm,
        )
    )
    story.append(Spacer(1, 10 * mm))

    # ========== WEAKNESS ANALYSIS ==========
    story.append(Paragraph("Weakness Analysis", h3_style))
    if weaknesses:
        weak_rows = [["Criterion", "Priority", "Issue", "Impact/Recommendation"]]
        for w in weaknesses:
            weak_rows.append(
                [
                    str(w.get("criterion", "Unknown"))[:25],
                    str(w.get("priority", "N/A"))[:12],
                    str(w.get("issue", "Weak alignment detected."))[:30],
                    str(w.get("impact", "Improve this section for better academic quality."))[:35],
                ]
            )
        weak_table = Table(weak_rows, colWidths=[35 * mm, 25 * mm, 50 * mm, 45 * mm])
        weak_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(weak_table)
    else:
        story.append(Paragraph("No major weaknesses detected.", body_style))
    story.append(Spacer(1, 10 * mm))

    # ========== RECOMMENDED RESOURCES ==========
    story.append(Paragraph("Recommended Learning Resources", h3_style))
    if recommendations:
        for criterion, resource_group in list(recommendations.items())[:5]:
            story.append(Paragraph(f"<b>{criterion}</b>", small_style))

            if isinstance(resource_group, dict):
                iter_pairs = []
                for cat in ("guides", "videos", "articles"):
                    for item in resource_group.get(cat, []) or []:
                        iter_pairs.append((cat, item))
            elif isinstance(resource_group, list):
                iter_pairs = [("resources", item) for item in resource_group]
            else:
                iter_pairs = []

            if not iter_pairs:
                story.append(Paragraph("No resources available.", small_style))
                story.append(Spacer(1, 2 * mm))
                continue

            for category, item in iter_pairs[:3]:
                if isinstance(item, str):
                    story.append(Paragraph(f"• {category.title()}: {item[:70]}", small_style))
                elif isinstance(item, dict):
                    title = (item.get("title") or item.get("name") or "Resource")[:50]
                    url = item.get("url") or ""
                    typ = item.get("type") or category
                    if url:
                        story.append(
                            Paragraph(
                                f"• {str(typ).title()}: <link href=\"{url}\">{title}</link>",
                                small_style,
                            )
                        )
                    else:
                        story.append(Paragraph(f"• {str(typ).title()}: {title}", small_style))
            story.append(Spacer(1, 4 * mm))
    else:
        story.append(Paragraph("No recommendations available yet.", body_style))

    story.append(Spacer(1, 8 * mm))

    # ========== RECOMMENDED NEXT STEPS ==========
    story.append(Paragraph("Recommended Next Steps", h3_style))
    if next_steps:
        for step in next_steps:
            week_text = step.get("week", "Step")
            action_text = step.get("action", "Continue improvement.")
            story.append(Paragraph(f"<b>{week_text}:</b> {action_text}", body_style))
    else:
        story.append(Paragraph("No improvement plan available. Continue iterative report improvements.", body_style))

    # ========== PAGE NUMBERS & FOOTER ==========
    def _draw_page_number(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        
        # Page number
        canvas.drawRightString(A4[0] - 14 * mm, 10 * mm, f"Page {document.page}")
        
        # Footer line
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.5)
        canvas.line(14 * mm, 12 * mm, A4[0] - 14 * mm, 12 * mm)
        
        # Document timestamp
        canvas.drawString(14 * mm, 10 * mm, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        canvas.restoreState()

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
