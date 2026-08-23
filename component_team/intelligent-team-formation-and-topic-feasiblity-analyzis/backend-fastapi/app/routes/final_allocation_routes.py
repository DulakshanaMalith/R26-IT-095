from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.final_allocation import FinalAllocationCreateRequest
from app.services.final_allocation_export_service import build_excel_export, build_pdf_export
from app.services.final_allocation_service import create_final_allocation, get_final_allocation

router = APIRouter(prefix="/api/final-allocations", tags=["Final Allocations"])

@router.post("", status_code=201)
def save_final_allocation(request: FinalAllocationCreateRequest, db: Session = Depends(get_db)):
    try:
        allocation = create_final_allocation(db, request)
        return {"success": True, "message": "Final allocation saved successfully.", "allocation": allocation}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Final allocation could not be saved. {str(exc)}")

@router.get("/{allocation_id}")
def read_final_allocation(allocation_id: str, db: Session = Depends(get_db)):
    allocation = get_final_allocation(db, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Final allocation was not found.")
    return {"success": True, "allocation": allocation}

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
