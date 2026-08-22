from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import shutil
import logging
import traceback
from copy import deepcopy

from src.preprocessing.pdf_extractor import extract_text_from_pdf
from src.preprocessing.text_cleaner import clean_text
from src.preprocessing.section_splitter import split_sections
from src.utils.file_utils import load_json, extract_student_id_from_text
from src.grading.rubric_matcher import match_rubric
from src.grading.score_calculator import calculate_scores
from src.grading.ml_predictor import predict_ml_score, ML_SCORE_CAP
from src.grading.final_score import calculate_final_hybrid_score, SEMANTIC_WEIGHT, ML_WEIGHT
from src.diagnosis.weakness_detector import detect_weaknesses
from src.evaluation.progress_tracker import update_student_progress
from src.recommendation.recommender import recommend_resources
from src.feedback.feedback_generator import generate_feedback
from src.utils.pdf_exporter import save_feedback_as_pdf
from src.utils.model_metrics_loader import load_latest_model_metrics
from src.analytics.supervisor_dashboard import build_supervisor_dashboard

app = FastAPI(title="Adaptive Mentorship API")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("data/raw/reports")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PDF = Path("outputs/feedback_report.pdf")
LAST_REPORT_PAYLOAD = None

@app.get("/")
async def root():
    return {"message": "Adaptive Mentorship API is running"}


@app.get("/supervisor-dashboard")
async def supervisor_dashboard(version_filter: str | None = None):
    """
    Get supervisor analytics dashboard.
    
    Args:
        version_filter: Optional query parameter to filter by specific version
                       (e.g., "Version 2"). If provided, only analytics for that
                       version are included.
    
    Returns:
        Aggregated analytics metrics based on latest records per student+version
    """
    try:
        return build_supervisor_dashboard(version_filter=version_filter)
    except Exception as exc:
        logger.exception("Supervisor dashboard generation failed")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Supervisor dashboard generation failed.",
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )


@app.post("/detect-student-id")
async def detect_student_id(file: UploadFile = File(...)):
    """Lightweight endpoint to extract a student ID from an uploaded PDF.

    This avoids running full analysis when the frontend only needs to auto-fill
    the Student ID field on upload.
    """
    try:
        file_path = UPLOAD_DIR / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        raw_text = extract_text_from_pdf(str(file_path))
        cleaned_text = clean_text(raw_text)
        detected_student_id = extract_student_id_from_text(cleaned_text)

        return {"detected_student_id": detected_student_id}
    except Exception as exc:
        logger.exception("Student ID detection failed")
        return JSONResponse(status_code=500, content={"detail": "Detection failed", "error": str(exc)})

@app.post("/analyze")
async def analyze_report(
    file: UploadFile = File(...),
    student_id: str = Form("N/A"),
    version: str = Form("Version 1"),
):
    global LAST_REPORT_PAYLOAD
    try:
        file_path = UPLOAD_DIR / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        rubric_path = "data/raw/rubric/rubric.json"

        raw_text = extract_text_from_pdf(str(file_path))
        cleaned_text = clean_text(raw_text)

        # Attempt to auto-detect student ID from the extracted PDF text.
        detected_student_id = extract_student_id_from_text(cleaned_text)
        sections = split_sections(cleaned_text)

        rubric = load_json(rubric_path)
        rubric_results = match_rubric(sections, rubric)
        score_summary = calculate_scores(rubric_results, rubric)

        ml_result = predict_ml_score(cleaned_text)

        # Decide which student id to use for recording progress: prefer the
        # explicitly provided form value if present; otherwise fall back to the
        # auto-detected value. This ensures manual override remains possible.
        provided_student_id = (student_id or "").strip()
        if provided_student_id and provided_student_id.upper() != "N/A":
            confirmed_student_id = provided_student_id
        else:
            confirmed_student_id = detected_student_id or provided_student_id

        hybrid_result = calculate_final_hybrid_score(
            semantic_score=score_summary["overall_score"],
            ml_score=ml_result["normalized_ml_score"],
        )

        scoring_policy = {
            "semantic_weight": SEMANTIC_WEIGHT,
            "ml_weight": ML_WEIGHT,
            "ml_score_cap": ML_SCORE_CAP,
            "normalization": "ml_raw_0_to_6_scaled_to_0_to_100_then_capped",
        }

        weaknesses = detect_weaknesses(rubric_results, threshold=0.50)

        try:
            progress_result = update_student_progress(
                student_id=confirmed_student_id,
                version=version,
                final_score=hybrid_result.get("final_score", 0),
                semantic_score=score_summary.get("overall_score", 0),
                ml_score=ml_result.get("normalized_ml_score", 0),
                grade=hybrid_result.get("grade"),
                status=hybrid_result.get("status"),
                section_scores=score_summary.get("section_scores", []),
                weaknesses=weaknesses,
            )
        except Exception:
            traceback.print_exc()
            progress_result = {
                "previous_score": None,
                "latest_score": hybrid_result.get("final_score", 0),
                "improvement": 0,
                "message": "Progress tracking is unavailable right now.",
            }

        recommendations = recommend_resources(weaknesses)

        feedback_data = generate_feedback(
            rubric_results=rubric_results,
            weaknesses=weaknesses,
            recommendations=recommendations,
            score_summary=score_summary,
            ml_result=ml_result,
            hybrid_result=hybrid_result,
            scoring_policy=scoring_policy,
        )

        feedback_data["scoring_policy"] = scoring_policy

        # Expose detected student id back to the frontend so it can auto-fill
        # the upload form. The header/student id for the report should reflect
        # the final confirmed id that will be used for progress tracking.
        feedback_data["detected_student_id"] = detected_student_id

        if "header" in feedback_data:
            feedback_data["header"]["student_id"] = confirmed_student_id
            feedback_data["header"]["version"] = version

        # Keep section score details for export table generation.
        feedback_data["section_scores"] = score_summary.get("section_scores", [])
        LAST_REPORT_PAYLOAD = deepcopy(feedback_data)

        return {
            "header": feedback_data.get("header", {}),
            "text": feedback_data.get("text", ""),
            "score_summary": score_summary,
            "ml_result": ml_result,
            "model_metrics": load_latest_model_metrics(),
            "hybrid_result": hybrid_result,
            "scoring_policy": feedback_data.get("scoring_policy", {}),
            "progress_result": progress_result,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "rubric_results": rubric_results,
        }

    except Exception as exc:
        logger.exception("Analysis failed during /analyze")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Analysis failed on the backend.",
                "message": str(exc),
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )


@app.get("/export-report")
async def export_report():
    if LAST_REPORT_PAYLOAD is None:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "No analysis data available. Run /analyze first before exporting the report."
            },
        )

    try:
        save_feedback_as_pdf(LAST_REPORT_PAYLOAD, str(OUTPUT_PDF))
        return FileResponse(
            path=str(OUTPUT_PDF),
            media_type="application/pdf",
            filename="feedback_report.pdf",
        )
    except Exception as exc:
        logger.exception("Report export failed during /export-report")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Report export failed on the backend.",
                "message": str(exc),
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            },
        )


@app.get("/download-pdf")
async def download_pdf():
    # Alias for existing frontend compatibility.
    return await export_report()