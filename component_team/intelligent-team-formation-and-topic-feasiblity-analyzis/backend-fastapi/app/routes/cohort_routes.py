import shutil
from pathlib import Path
from tempfile import (
    NamedTemporaryFile,
)

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.models.cohort_import import (
    ValidationReport,
)
from app.services.cohort_data_service import (
    build_cohort_import_data,
)
from app.services.nsga2_optimizer import (
    optimize_team_formation,
)
from app.services.team_formation_response_service import (
    build_staff_team_formation_response,
)
from app.services.workbook_validation_service import (
    validate_workbook,
)


router = APIRouter(
    prefix="/api/cohort",
    tags=["Cohort Import"],
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


@router.post(
    "/validate",
    response_model=ValidationReport,
)
async def validate_cohort_workbook(
    file: UploadFile = File(...),
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

        report = (
            validate_workbook(
                temp_path
            )
        )

        return report

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "The workbook could not "
                "be processed. "
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


@router.post(
    "/optimize",
)
async def optimize_cohort_teams(
    file: UploadFile = File(...),
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
                temp_path
            )
        )

        if not validation_report.valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        "Workbook validation "
                        "failed. Team formation "
                        "was not started."
                    ),
                    "validation": (
                        validation_report
                        .model_dump()
                    ),
                },
            )

        cohort_data = (
            build_cohort_import_data(
                temp_path
            )
        )

        optimization_result = (
            optimize_team_formation(
                data=cohort_data,
                population_size=120,
                generations=150,
                seed=42,
                seeded_initialization=True,
                seed_variant_count=12,
            )
        )

        decision_support = (
            build_staff_team_formation_response(
                data=cohort_data,
                optimization_result=(
                    optimization_result
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
            "team_formation": (
                decision_support
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
                "Team formation could "
                "not be completed. "
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