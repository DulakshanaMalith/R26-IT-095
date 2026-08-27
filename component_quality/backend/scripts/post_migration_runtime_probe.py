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
    env_path = BACKEND / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def file_fingerprints() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in [
        BACKEND / "data" / "analysis_history.json",
        BACKEND / "data" / "grading_history.json",
        BACKEND / "data" / "knowledge_graph_history.json",
    ]:
        data = path.read_bytes()
        result[path.name] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "mtime_ns": path.stat().st_mtime_ns,
        }
    return result


def table_counts(engine) -> dict[str, int]:
    tables = [
        "analysis_history_records",
        "grading_records",
        "knowledge_graph_records",
    ]
    with engine.connect() as conn:
        return {
            table_name: conn.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one()
            for table_name in tables
        }


def main() -> None:
    load_env()
    engine = create_engine(os.environ["DATABASE_URL"])
    before_hashes = file_fingerprints()
    before_counts = table_counts(engine)

    from fastapi.testclient import TestClient
    from src.api.main import app
    import src.api.routers.analysis as analysis_router
    import src.api.routers.knowledge_graph as graph_router
    import src.api.routers.resources as resources_router

    def local_resources(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
        return [{"title": "Verification resource", "url": "https://example.com/verification"}]

    def local_feedback(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {
                "tag": "methodology",
                "comment_text": "Add more evaluation detail.",
                "similarity_score": 0.99,
            }
        ]

    def local_prediction(*args: Any, **kwargs: Any) -> str:
        return "methodology"

    # Keep this probe focused on persistence; model latency and external recommendations are not migration checks.
    analysis_router.predict_tag = local_prediction
    analysis_router.retrieve_feedback = local_feedback
    analysis_router.get_recommended_resources = local_resources
    resources_router.get_recommended_resources = local_resources

    analysis_id = "VERIFY_" + uuid.uuid4().hex
    request_id = "REQ_" + uuid.uuid4().hex
    proposal_text = """
Title: PostgreSQL Verification for ResearchPilot Academic Proposal
Abstract: This proposal evaluates whether a migration from legacy runtime files to PostgreSQL preserves academic workflow evidence and historical analysis records.
Introduction: ResearchPilot supports students and supervisors by analyzing proposal drafts, grading readiness, recommending resources, and generating concept graphs.
Problem Statement: Runtime persistence must be reliable, queryable, and protected from accidental JSON corruption while maintaining existing API contracts.
Research Gap: Prior local persistence mixed SQLite workflow tables with JSON history files, making relational verification and analytics difficult.
Objectives: The study verifies analysis, grading, resource recommendation, knowledge graph extraction, and supervisor analytics after database migration.
Literature Review: Related work on educational technology platforms emphasizes durable audit trails, normalized workflow records, and preservation of historical payloads.
Methodology: The verification uses representative API calls, row count comparisons, Alembic schema checks, and payload preservation checks against migrated records.
Evaluation: Success is measured by unchanged frontend response shapes, increasing PostgreSQL history counts, stable legacy JSON file hashes, and no SQLite runtime dependency.
Ethical Considerations: The process avoids regenerating model outputs for historical records and preserves original student-facing evidence without inventing relationships.
Limitations: The verification uses a concise synthetic proposal and does not alter machine learning models, grading algorithms, Tavily integration, or frontend behavior.
References: PostgreSQL documentation, SQLAlchemy documentation, Alembic migration guidance, and ResearchPilot migration evidence reports.
"""

    endpoints: dict[str, dict[str, Any]] = {}
    started_at = time.perf_counter()
    with TestClient(app) as client:
        calls = [
            ("startup_root", "get", "/", None),
            (
                "analyze",
                "post",
                "/analyze",
                {
                    "analysis_id": analysis_id,
                    "request_id": request_id,
                    "text": proposal_text,
                    "source": "verification",
                    "filename": "post_migration_verification.txt",
                    "student_name": "Verification Student",
                    "student_id": "VERIFY-STUDENT",
                    "proposal_title": "PostgreSQL Verification Proposal",
                },
            ),
            (
                "grade_report",
                "post",
                "/grade-report",
                {
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "source": "verification",
                    "filename": "post_migration_verification.txt",
                },
            ),
            (
                "knowledge_graph",
                "post",
                "/knowledge-graph",
                {
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "filename": "post_migration_verification.txt",
                },
            ),
            (
                "recommend_resources",
                "post",
                "/recommend-resources",
                {
                    "analysis_id": analysis_id,
                    "text": proposal_text,
                    "feedback": "Improve methodology and evaluation detail.",
                },
            ),
            ("analysis_history", "get", "/analysis-history", None),
            ("grading_history", "get", "/grading-history", None),
            ("grading_analytics", "get", "/grading-analytics", None),
            ("supervisor_analytics", "get", "/supervisor-analytics", None),
        ]
        for name, method, url, body in calls:
            response = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
            endpoints[name] = {"status_code": response.status_code, "ok": response.status_code < 400}
            if response.status_code >= 400:
                try:
                    endpoints[name]["detail"] = response.json()
                except Exception:
                    endpoints[name]["detail"] = response.text[:500]

    after_hashes = file_fingerprints()
    after_counts = table_counts(engine)
    summary = {
        "analysis_id": analysis_id,
        "duration_seconds": round(time.perf_counter() - started_at, 2),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "count_deltas": {
            key: after_counts[key] - before_counts[key]
            for key in before_counts
        },
        "json_unchanged": before_hashes == after_hashes,
        "endpoint_results": endpoints,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
