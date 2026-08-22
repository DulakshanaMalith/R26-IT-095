import re
import shutil
from pathlib import Path
from tempfile import (
    NamedTemporaryFile,
)

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.services.cohort_data_service import (
    build_cohort_import_data,
)
from app.services.topic_feasibility_service import (
    analyze_topic_technical_feasibility,
)
from app.services.workbook_validation_service import (
    validate_workbook,
)


router = APIRouter(
    prefix="/api/topic-feasibility",
    tags=[
        "Topic Technical Feasibility"
    ],
)


ALLOWED_EXTENSIONS = {
    ".xlsx",
}


def _validate_upload(
    file: UploadFile,
) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail=(
                "No file was provided."
            ),
        )

    extension = Path(
        file.filename
    ).suffix.lower()

    if (
        extension
        not in ALLOWED_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid file type. "
                "Please upload an "
                ".xlsx workbook."
            ),
        )


def _save_upload_to_temp(
    file: UploadFile,
) -> Path:
    with NamedTemporaryFile(
        delete=False,
        suffix=".xlsx",
    ) as temp_file:
        temp_path = Path(
            temp_file.name
        )

        shutil.copyfileobj(
            file.file,
            temp_file,
        )

    return temp_path


def _parse_team_student_ids(
    raw_value: str,
) -> list[str]:
    return [
        value.strip()
        for value in re.split(
            r"[,;\n]+",
            raw_value,
        )
        if value.strip()
    ]


@router.post(
    "/analyze",
)
async def analyze_topic_feasibility(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    team_student_ids: str = Form(...),
    students_per_team: int = Form(...),
):
    _validate_upload(
        file
    )

    temp_path = None

    try:
        temp_path = (
            _save_upload_to_temp(
                file
            )
        )

        validation_report = (
            validate_workbook(
                temp_path,
                students_per_team=students_per_team,
            )
        )

        if not validation_report.valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Workbook validation "
                        "failed. Topic feasibility "
                        "analysis was not started."
                    ),
                    "validation": (
                        validation_report
                        .model_dump()
                    ),
                },
            )

        cohort_data = (
            build_cohort_import_data(
                temp_path,
                students_per_team=students_per_team,
            )
        )

        parsed_student_ids = (
            _parse_team_student_ids(
                team_student_ids
            )
        )

        result = (
            analyze_topic_technical_feasibility(
                data=cohort_data,
                project_id=project_id,
                team_student_ids=(
                    parsed_student_ids
                ),
                students_per_team=(
                    students_per_team
                ),
            )
        )

        return {
            "success": True,
            "validation": (
                validation_report
                .model_dump()
            ),
            "cohort": {
                "student_count": len(
                    cohort_data.students
                ),
                "project_count": len(
                    cohort_data.projects
                ),
                "requirement_count": len(
                    cohort_data
                    .project_requirements
                ),
            },
            "topic_feasibility": (
                result
            ),
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Topic technical feasibility "
                "analysis could not be "
                "completed. "
                f"{str(exc)}"
            ),
        )

    finally:
        await file.close()

        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()