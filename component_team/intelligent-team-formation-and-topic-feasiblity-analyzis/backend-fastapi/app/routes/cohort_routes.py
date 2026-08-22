import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.models.cohort_import import ValidationReport
from app.routes.topic_feasibility_routes import router as topic_feasibility_router
from app.services.cohort_data_service import build_cohort_import_data
from app.services.dynamic_team_formation_service import optimize_with_staff_team_size
from app.services.workbook_validation_service import validate_workbook

router = APIRouter()
cohort_router = APIRouter(prefix="/api/cohort", tags=["Cohort Import"])
ALLOWED_EXTENSIONS = {".xlsx"}

def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was provided.")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an .xlsx workbook.")

def _validate_team_size(students_per_team: int) -> None:
    if students_per_team < 2:
        raise HTTPException(status_code=422, detail="Students per team must be at least 2.")

def _save_upload_to_temp(file: UploadFile) -> Path:
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
        temp_path = Path(temp_file.name)
        shutil.copyfileobj(file.file, temp_file)
    return temp_path

def _elapsed(start: float) -> float:
    return round(perf_counter() - start, 4)

@cohort_router.post("/validate", response_model=ValidationReport)
async def validate_cohort_workbook(
    file: UploadFile = File(...),
    students_per_team: int = Form(...),
):
    _validate_upload(file)
    _validate_team_size(students_per_team)
    temp_path = None
    try:
        temp_path = _save_upload_to_temp(file)
        return validate_workbook(temp_path, students_per_team=students_per_team)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"The workbook could not be processed. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

@cohort_router.post("/optimize")
async def optimize_cohort_teams(
    file: UploadFile = File(...),
    students_per_team: int = Form(...),
):
    request_start = perf_counter()
    _validate_upload(file)
    _validate_team_size(students_per_team)
    temp_path = None
    try:
        save_start = perf_counter()
        temp_path = _save_upload_to_temp(file)
        upload_save_seconds = _elapsed(save_start)
        validation_start = perf_counter()
        validation_report = validate_workbook(temp_path, students_per_team=students_per_team)
        validation_seconds = _elapsed(validation_start)
        if not validation_report.valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Workbook validation failed. Team formation was not started.",
                    "validation": validation_report.model_dump(),
                },
            )
        data_start = perf_counter()
        cohort_data = build_cohort_import_data(temp_path, students_per_team=students_per_team)
        cohort_data_build_seconds = _elapsed(data_start)
        formation_start = perf_counter()
        decision_support = optimize_with_staff_team_size(
            data=cohort_data,
            students_per_team=students_per_team,
            population_size=120,
            generations=150,
            seed=42,
            seeded_initialization=True,
            seed_variant_count=12,
        )
        team_formation_pipeline_seconds = _elapsed(formation_start)
        request_processing_seconds = _elapsed(request_start)
        return {
            "success": True,
            "validation": validation_report.model_dump(),
            "cohort": {
                "student_count": len(cohort_data.students),
                "project_count": len(cohort_data.projects),
                "requirement_count": len(cohort_data.project_requirements),
                "students_per_team": students_per_team,
            },
            "runtime": {
                "upload_save_seconds": upload_save_seconds,
                "initial_validation_seconds": validation_seconds,
                "cohort_data_build_seconds": cohort_data_build_seconds,
                "team_formation_pipeline_seconds": team_formation_pipeline_seconds,
                "request_processing_seconds_before_fastapi_serialization": request_processing_seconds,
                "note": "cohort_data_build_seconds includes the current internal validation performed by build_cohort_import_data. FastAPI JSON serialization and browser rendering occur after this timing block.",
            },
            "team_formation": decision_support,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Team formation could not be completed. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

router.include_router(cohort_router)
router.include_router(topic_feasibility_router)
