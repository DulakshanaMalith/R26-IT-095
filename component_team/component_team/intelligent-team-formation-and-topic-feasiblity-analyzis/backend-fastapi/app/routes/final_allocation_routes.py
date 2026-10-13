import json
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.db_models.final_allocation import FinalAllocation
from app.models.final_allocation import FinalAllocationCreateRequest
from app.services.cohort_data_service import build_cohort_import_data
from app.services.final_allocation_export_service import build_excel_export, build_pdf_export
from app.services.final_allocation_revision_service import build_editable_allocation_workbook, create_revised_allocation, validate_revision_workbook
from app.services.final_allocation_service import attach_reference_data, create_final_allocation, get_active_final_allocation, get_active_supervisor_groups, get_active_team_data, get_final_allocation, get_supervisor_groups

router = APIRouter(prefix="/api/final-allocations", tags=["Final Allocations"])

def _save_upload(file: UploadFile) -> Path:
    if not file.filename or Path(file.filename).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail="Please upload a valid .xlsx workbook.")
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
        temp_path = Path(temp_file.name)
        shutil.copyfileobj(file.file, temp_file)
    return temp_path

def _reference_data_from_workbook(file_path: Path, students_per_team: int) -> dict:
    cohort_data = build_cohort_import_data(file_path, students_per_team=students_per_team)
    if hasattr(cohort_data, "model_dump"):
        return cohort_data.model_dump(mode="json")
    raise ValueError("The cohort data object could not be serialized for revision support.")

@router.post("", status_code=201)
def save_final_allocation(request: FinalAllocationCreateRequest, db: Session = Depends(get_db)):
    try:
        allocation = create_final_allocation(db, request)
        return {"success": True, "message": "Final allocation saved and marked ACTIVE. Revision support requires saving with the source workbook.", "allocation": allocation}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Final allocation could not be saved. {str(exc)}")

@router.post("/with-source", status_code=201)
async def save_final_allocation_with_source(payload_json: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = None
    try:
        request = FinalAllocationCreateRequest.model_validate(json.loads(payload_json))
        temp_path = _save_upload(file)
        reference_data = _reference_data_from_workbook(temp_path, request.students_per_team)
        allocation = create_final_allocation(db, request, reference_data=reference_data)
        return {"success": True, "message": "Final allocation saved as ACTIVE with source reference data. Editable revision workflow is enabled.", "allocation": allocation}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Final allocation could not be saved with source workbook. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

@router.get("/active")
def read_active_final_allocation(db: Session = Depends(get_db)):
    allocation = get_active_final_allocation(db)
    if allocation is None:
        raise HTTPException(status_code=404, detail="No ACTIVE final allocation was found.")
    return {"success": True, "allocation": allocation}

@router.get("/active/teams")
def read_active_team_data(db: Session = Depends(get_db)):
    data = get_active_team_data(db)
    if data is None:
        raise HTTPException(status_code=404, detail="No ACTIVE final allocation was found.")
    return {"success": True, **data}

@router.get("/active/supervisors/{supervisor_id}/groups")
def read_active_supervisor_groups(supervisor_id: str, db: Session = Depends(get_db)):
    groups = get_active_supervisor_groups(db, supervisor_id)
    if groups is None:
        raise HTTPException(status_code=404, detail="No ACTIVE final allocation was found.")
    return {"success": True, "allocation_status": "ACTIVE", **groups}

@router.post("/revisions/validate")
async def validate_uploaded_revision(parent_allocation_id: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = None
    try:
        temp_path = _save_upload(file)
        preview = validate_revision_workbook(db, parent_allocation_id, temp_path)
        preview.pop("_solution", None)
        preview.pop("_supervisor_assignments", None)
        return {"success": True, **preview}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revision workbook validation failed. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

@router.post("/revisions/confirm", status_code=201)
async def confirm_uploaded_revision(parent_allocation_id: str = Form(...), change_reason: str = Form(""), file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = None
    try:
        temp_path = _save_upload(file)
        result = create_revised_allocation(db, parent_allocation_id, temp_path, file.filename, change_reason)
        return {
            "success": True,
            "message": "Revised allocation validated and saved as the new ACTIVE allocation. The parent allocation was archived.",
            **result,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Revised allocation could not be confirmed. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

@router.post("/{allocation_id}/reference-workbook")
async def attach_original_reference_workbook(allocation_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = None
    try:
        allocation = get_final_allocation(db, allocation_id)
        if allocation is None:
            raise HTTPException(status_code=404, detail="Final allocation was not found.")
        temp_path = _save_upload(file)
        reference_data = _reference_data_from_workbook(temp_path, allocation["students_per_team"])
        updated = attach_reference_data(db, allocation_id, reference_data)
        return {"success": True, "message": "Original cohort source data attached. Editable revision workflow is now enabled for this allocation.", "allocation": updated}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reference workbook could not be attached. {str(exc)}")
    finally:
        await file.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

@router.get("/{allocation_id}/editable.xlsx")
def download_editable_allocation(allocation_id: str, db: Session = Depends(get_db)):
    allocation = get_final_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    model = db.get(FinalAllocation, allocation_id)
    try:
        output = build_editable_allocation_workbook(allocation, model.reference_data if model else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    filename = f"{allocation_id}_editable_allocation_revision.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@router.get("/{allocation_id}")
def read_final_allocation(allocation_id: str, db: Session = Depends(get_db)):
    allocation = get_final_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    return {"success": True, "allocation": allocation}

@router.get("/{allocation_id}/supervisors/{supervisor_id}/groups")
def read_supervisor_groups(allocation_id: str, supervisor_id: str, db: Session = Depends(get_db)):
    groups = get_supervisor_groups(db, allocation_id, supervisor_id)
    if groups is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    return {"success": True, **groups}

@router.get("/{allocation_id}/export.xlsx")
def export_final_allocation_excel(allocation_id: str, db: Session = Depends(get_db)):
    allocation = get_final_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    output = build_excel_export(allocation)
    filename = f"{allocation_id}_final_team_allocation.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@router.get("/{allocation_id}/export.pdf")
def export_final_allocation_pdf(allocation_id: str, db: Session = Depends(get_db)):
    allocation = get_final_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    output = build_pdf_export(allocation)
    filename = f"{allocation_id}_final_team_allocation.pdf"
    return StreamingResponse(output, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
