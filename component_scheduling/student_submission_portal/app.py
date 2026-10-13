"""Standalone student document-submission portal (default port 8010)."""
from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from integration_security import submission_integration_key


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SCHEDULING_API_URL = os.getenv("SCHEDULING_API_URL", "http://127.0.0.1:8000").rstrip("/")
MAX_FILE_BYTES = int(os.getenv("IPMS_MAX_SUBMISSION_BYTES", str(20 * 1024 * 1024)))

# This demonstration portal accepts a typed student ID, not a verified student
# session. Do not expose it as a production submission service.
if os.getenv("IPMS_ENV", "").strip().lower() == "production":
    raise RuntimeError("The test-only student submission portal requires verified student login before production use.")

app = FastAPI(title="IPMS Student Document Submission Portal")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="submission-static")


def _normalise_group_id(project_id: str) -> str:
    """Accept the standard group ID with or without suffix zero-padding."""
    value = (project_id or "").strip()
    standard_group = re.fullmatch(r"(R\d{2}-[A-Za-z]+-)(\d{1,3})", value, re.I)
    if standard_group:
        return f"{standard_group.group(1).upper()}{standard_group.group(2).zfill(3)}"
    return value


def _upstream_error(response: httpx.Response) -> HTTPException:
    try:
        detail = response.json().get("detail") or response.json().get("message")
    except (ValueError, AttributeError):
        detail = None
    return HTTPException(status_code=response.status_code, detail=detail or "Scheduling service rejected the request.")


@app.get("/")
def portal_home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/health")
async def portal_health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{SCHEDULING_API_URL}/api/health")
        return {"status": "healthy" if response.is_success else "degraded",
                "scheduling_api": SCHEDULING_API_URL,
                "scheduling_status": response.status_code}
    except httpx.RequestError:
        return {"status": "degraded", "scheduling_api": SCHEDULING_API_URL,
                "scheduling_status": "unreachable"}


@app.get("/api/document-tasks")
async def document_tasks(project_id: str, student_id: str):
    project_id = _normalise_group_id(project_id)
    student_id = student_id.strip().upper()
    if not project_id or not student_id:
        raise HTTPException(status_code=422, detail="Group ID and Student ID are required.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{SCHEDULING_API_URL}/api/integrations/projects/{project_id}/document-tasks",
                params={"student_id": student_id},
                headers={"X-IPMS-Integration-Key": submission_integration_key()},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Scheduling service is not running on port 8000.") from exc
    if not response.is_success:
        raise _upstream_error(response)
    return response.json()


@app.post("/api/submit")
async def submit_document(
    project_id: str = Form(...), task_id: int = Form(...), student_id: str = Form(...),
    file: UploadFile = File(...),
):
    project_id = _normalise_group_id(project_id)
    student_id = student_id.strip().upper()
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"Document exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB.")
    files = {"file": (Path(file.filename or "submission").name, content,
                      file.content_type or "application/octet-stream")}
    data = {"project_id": project_id, "task_id": str(task_id),
            "student_id": student_id}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{SCHEDULING_API_URL}/api/integrations/document-submissions",
                data=data, files=files,
                headers={"X-IPMS-Integration-Key": submission_integration_key()},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Scheduling service is not running on port 8000.") from exc
    if not response.is_success:
        raise _upstream_error(response)
    return response.json()
