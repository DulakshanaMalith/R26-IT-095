import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models.cohort_import import ValidationReport
from app.services.workbook_validation_service import validate_workbook

router = APIRouter(
    prefix="/api/cohort",
    tags=["Cohort Import"],
)

ALLOWED_EXTENSIONS = {".xlsx"}

@router.post(
    "/validate",
    response_model=ValidationReport,
)
async def validate_cohort_workbook(
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file was provided.",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid file type. "
                "Please upload an .xlsx workbook."
            ),
        )

    temp_path = None

    try:
        with NamedTemporaryFile(
            delete=False,
            suffix=".xlsx",
        ) as temp_file:
            temp_path = Path(temp_file.name)

            shutil.copyfileobj(
                file.file,
                temp_file,
            )

        report = validate_workbook(
            temp_path
        )

        return report

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "The workbook could not be processed. "
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