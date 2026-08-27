from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def load_env() -> None:
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def fingerprints() -> dict[str, dict[str, Any]]:
    result = {}
    for name in ["analysis_history.json", "grading_history.json", "knowledge_graph_history.json"]:
        path = BACKEND / "data" / name
        data = path.read_bytes()
        result[name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "mtime_ns": path.stat().st_mtime_ns,
        }
    return result


def counts(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {
            table_name: conn.execute(text("SELECT count(*) FROM " + table_name)).scalar_one()
            for table_name in [
                "analysis_history_records",
                "grading_records",
                "knowledge_graph_records",
            ]
        }


def main() -> None:
    load_env()
    engine = create_engine(os.environ["DATABASE_URL"])
    before_hashes = fingerprints()
    before_counts = counts(engine)
    analysis_id = "REAL_VERIFY_" + uuid.uuid4().hex
    request_id = "REQ_" + uuid.uuid4().hex
    proposal_text = """
Title: PostgreSQL Runtime Verification for ResearchPilot
Abstract: This research proposal verifies that ResearchPilot persists analysis, grading, and graph history in PostgreSQL after migration.
Introduction: Academic proposal review platforms require durable evidence, repeatable analytics, and clear supervisor workflows.
Problem Statement: The previous persistence design used legacy files, so runtime verification must prove that new API requests write to PostgreSQL.
Research Gap: Existing demonstrations often verify schema creation without confirming complete application endpoint behavior after migration.
Objectives: The objectives are to run real analysis, grading, recommendation, and knowledge graph requests while preserving frontend response contracts.
Literature Review: Prior educational technology research discusses structured feedback, proposal quality assessment, and version-aware academic support.
Methodology: This verification submits representative proposal text through FastAPI endpoints and checks database row count changes afterward.
Evaluation: Success is measured by successful HTTP responses, recommended resources in the analysis response, inserted PostgreSQL rows, and unchanged JSON files.
Ethical Considerations: The verification uses synthetic text and does not regenerate or alter historical migrated records.
Limitations: The test validates runtime persistence and representative endpoint behavior but does not change machine learning models or frontend behavior.
References: SQLAlchemy documentation, Alembic documentation, PostgreSQL documentation, and ResearchPilot migration evidence.
"""

    from fastapi.testclient import TestClient
    from src.api.main import app

    started = time.perf_counter()
    with TestClient(app) as client:
        responses = {
            "analyze": client.post(
                "/analyze",
                json={
                    "analysis_id": analysis_id,
                    "request_id": request_id,
                    "text": proposal_text,
                    "source": "real-verification",
                    "filename": "real_post_migration_verification.txt",
                    "student_name": "Real Verification Student",
                    "student_id": "REAL-VERIFY-STUDENT",
                    "proposal_title": "PostgreSQL Runtime Verification",
                },
            ),
            "grade_report": client.post(
                "/grade-report",
                json={
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "source": "real-verification",
                    "filename": "real_post_migration_verification.txt",
                },
            ),
            "knowledge_graph": client.post(
                "/knowledge-graph",
                json={
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "filename": "real_post_migration_verification.txt",
                },
            ),
            "recommend_resources": client.post(
                "/recommend-resources",
                json={
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "feedback": "Improve methodology and evaluation evidence.",
                },
            ),
            "analysis_history": client.get("/analysis-history"),
            "grading_history": client.get("/grading-history"),
            "grading_analytics": client.get("/grading-analytics"),
            "supervisor_analytics": client.get("/supervisor-analytics"),
        }

    after_hashes = fingerprints()
    after_counts = counts(engine)
    endpoint_results = {}
    for name, response in responses.items():
        body: Any
        try:
            body = response.json()
        except Exception:
            body = response.text[:500]
        endpoint_results[name] = {
            "status_code": response.status_code,
            "ok": response.status_code < 400,
            "body_keys": sorted(body.keys()) if isinstance(body, dict) else None,
            "recommended_resource_count": len(body.get("recommended_resources", [])) if isinstance(body, dict) else None,
            "resources_count": len(body.get("resources", [])) if isinstance(body, dict) else None,
            "detail": body if response.status_code >= 400 else None,
        }
    summary = {
        "analysis_id": analysis_id,
        "duration_seconds": round(time.perf_counter() - started, 2),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "count_deltas": {key: after_counts[key] - before_counts[key] for key in before_counts},
        "json_unchanged": before_hashes == after_hashes,
        "endpoint_results": endpoint_results,
    }
    output_path = BACKEND / "data" / "post_migration_real_api_probe_result.json"
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
