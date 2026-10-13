import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.cohort_data_service import build_cohort_import_data
from app.services.project_pool_selection_service import scope_cohort_to_projects
from app.services.supervisor_allocation_service import allocate_supervisors
from app.services.team_size_configuration_service import calculate_team_configuration
from app.services.workbook_validation_service import validate_workbook

router = APIRouter(prefix="/api/supervisor-allocation", tags=["Supervisor Allocation"])
ALLOWED_EXTENSIONS = {".xlsx"}


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was provided.")
    if Path(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an .xlsx workbook.",
        )


def _save_upload_to_temp(file: UploadFile) -> Path:
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
        temp_path = Path(temp_file.name)
        shutil.copyfileobj(file.file, temp_file)
    return temp_path


def _parse_selected_project_ids(raw_value: str) -> list[str]:
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="selected_project_ids must be a JSON array of project IDs.",
        ) from exc

    if not isinstance(parsed, list) or not parsed:
        raise HTTPException(
            status_code=422,
            detail="selected_project_ids must contain at least one project ID.",
        )

    normalized: list[str] = []
    for value in parsed:
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=422,
                detail="Every selected project ID must be a non-empty string.",
            )
        normalized.append(value.strip().upper())

    if len(set(normalized)) != len(normalized):
        raise HTTPException(
            status_code=422,
            detail="Selected project IDs must be unique.",
        )

    return normalized


@router.post("/allocate")
async def allocate_project_supervisors(
    file: UploadFile = File(...),
    students_per_team: int = Form(...),
    selected_project_ids: str | None = Form(None),
):
    _validate_upload(file)
    if students_per_team < 2:
        raise HTTPException(
            status_code=422,
            detail="Students per team must be at least 2.",
        )

    temp_path = None

    try:
        temp_path = _save_upload_to_temp(file)
        validation_report = validate_workbook(
            temp_path,
            students_per_team=students_per_team,
        )
        if not validation_report.valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Workbook validation failed. Supervisor allocation was not started."
                    ),
                    "validation": validation_report.model_dump(),
                },
            )

        cohort_data = build_cohort_import_data(
            temp_path,
            students_per_team=students_per_team,
        )
        configuration = calculate_team_configuration(
            student_count=len(cohort_data.students),
            project_count=len(cohort_data.projects),
            students_per_team=students_per_team,
        )
        required_team_count = configuration["required_team_count"]

        if selected_project_ids is None or not selected_project_ids.strip():
            if configuration["surplus_project_count"] > 0:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "selected_project_ids is required when the workbook contains "
                        "more approved projects than the selected allocation needs."
                    ),
                )
            selected_ids = [project.project_id for project in cohort_data.projects]
        else:
            selected_ids = _parse_selected_project_ids(selected_project_ids)

        if len(selected_ids) != required_team_count:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"The selected allocation must contain exactly {required_team_count} "
                    f"unique projects, but {len(selected_ids)} project IDs were provided."
                ),
            )

        available_project_ids = {
            project.project_id.upper() for project in cohort_data.projects
        }
        unknown_project_ids = [
            project_id
            for project_id in selected_ids
            if project_id not in available_project_ids
        ]
        if unknown_project_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Selected allocation contains project IDs that are not approved in "
                    f"the uploaded workbook: {', '.join(unknown_project_ids)}."
                ),
            )

        scoped_data = scope_cohort_to_projects(cohort_data, selected_ids)
        allocation = allocate_supervisors(data=scoped_data)
        unassigned_project_ids = [
            project.project_id
            for project in cohort_data.projects
            if project.project_id.upper() not in set(selected_ids)
        ]

        return {
            "success": True,
            "validation": validation_report.model_dump(),
            "selected_project_ids": selected_ids,
            "unassigned_project_ids": unassigned_project_ids,
            "supervisor_allocation": allocation,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Supervisor allocation could not be completed. {str(exc)}",
        ) from exc
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
