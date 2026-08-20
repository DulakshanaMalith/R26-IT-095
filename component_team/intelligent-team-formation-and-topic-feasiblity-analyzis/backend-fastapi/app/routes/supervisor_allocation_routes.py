import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.services.cohort_data_service import (
    build_cohort_import_data,
)
from app.services.supervisor_allocation_service import (
    allocate_supervisors,
)
from app.services.workbook_validation_service import (
    validate_workbook,
)


router = APIRouter(
    prefix="/api/supervisor-allocation",
    tags=["Supervisor Allocation"],
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
            detail="No file was provided.",
        )

    extension = Path(
        file.filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
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


@router.post("/allocate")
async def allocate_project_supervisors(
    file: UploadFile = File(...),
):
    _validate_upload(file)

    temp_path = None

    try:
        temp_path = _save_upload_to_temp(
            file
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
                        "failed. Supervisor "
                        "allocation was not "
                        "started."
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

        allocation = (
            allocate_supervisors(
                data=cohort_data
            )
        )

        return {
            "success": True,
            "validation": (
                validation_report
                .model_dump()
            ),
            "supervisor_allocation": (
                allocation
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
                "Supervisor allocation "
                "could not be completed. "
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