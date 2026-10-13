"""Validate and migrate ResearchPilot SQLite/JSON persistence to PostgreSQL.

Run validation only:
    python scripts/migrate_to_postgres.py --validate-only

Run migration after `alembic upgrade head`:
    python scripts/migrate_to_postgres.py --migrate
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, insert, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.history_repositories import _analysis_model, _grading_model, _graph_model
from src.db.models.history import AnalysisHistoryRecord, GradingRecord, KnowledgeGraphRecord
from src.db.session import get_session_factory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
WORKFLOW_TABLES = [
    "users",
    "supervisor_profiles",
    "students",
    "supervisor_student_assignments",
    "proposals",
    "proposal_versions",
    "analyses",
    "supervisor_reviews",
    "ai_supervisor_review_drafts",
    "supervisor_review_drafts",
    "notification_logs",
]


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(payload, list):
        raise ValueError(f"{path} does not contain a JSON list.")
    return [item for item in payload if isinstance(item, dict)]


def _record_analysis_id(record: dict[str, Any]) -> str | None:
    value = record.get("analysis_id") or record.get("id")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _sqlite_rows(sqlite_path: Path, table: str) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]
    finally:
        connection.close()


def _sqlite_schema(sqlite_path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {
            "tables": tables,
            "columns": {
                table: [dict(row) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
                for table in tables
            },
            "counts": {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables
            },
        }
    finally:
        connection.close()


def validate_sources(data_dir: Path, sqlite_path: Path) -> dict[str, Any]:
    analysis_history = _load_json(data_dir / "analysis_history.json")
    grading_history = _load_json(data_dir / "grading_history.json")
    graph_history = _load_json(data_dir / "knowledge_graph_history.json")
    schema = _sqlite_schema(sqlite_path)

    sqlite_analysis_ids = {row["analysis_id"] for row in _sqlite_rows(sqlite_path, "analyses")}
    analysis_ids = [_record_analysis_id(record) for record in analysis_history if _record_analysis_id(record)]
    grading_ids = [_record_analysis_id(record) for record in grading_history if _record_analysis_id(record)]
    graph_ids = [_record_analysis_id(record) for record in graph_history if _record_analysis_id(record)]

    def duplicate_ids(values: list[str]) -> list[str]:
        return sorted([value for value, count in Counter(values).items() if count > 1])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sqlite_schema": schema,
        "source_counts": {
            "sqlite_analyses": len(sqlite_analysis_ids),
            "analysis_history": len(analysis_history),
            "grading_history": len(grading_history),
            "knowledge_graph_history": len(graph_history),
        },
        "identifier_validation": {
            "analysis_history_ids": {"total": len(analysis_ids), "unique": len(set(analysis_ids)), "duplicates": duplicate_ids(analysis_ids)},
            "grading_history_ids": {"total": len(grading_ids), "unique": len(set(grading_ids)), "duplicates": duplicate_ids(grading_ids)},
            "knowledge_graph_history_ids": {"total": len(graph_ids), "unique": len(set(graph_ids)), "duplicates": duplicate_ids(graph_ids)},
            "analysis_history_matches_sqlite": len(set(analysis_ids) & sqlite_analysis_ids),
            "analysis_history_orphaned_from_sqlite": len(set(analysis_ids) - sqlite_analysis_ids),
            "grading_matches_sqlite": len(set(grading_ids) & sqlite_analysis_ids),
            "grading_orphaned_from_sqlite": len(set(grading_ids) - sqlite_analysis_ids),
            "grading_matches_analysis_history": len(set(grading_ids) & set(analysis_ids)),
            "grading_orphaned_from_analysis_history": len(set(grading_ids) - set(analysis_ids)),
            "knowledge_graph_matches_sqlite": len(set(graph_ids) & sqlite_analysis_ids),
            "knowledge_graph_orphaned_from_sqlite": len(set(graph_ids) - sqlite_analysis_ids),
            "knowledge_graph_matches_analysis_history": len(set(graph_ids) & set(analysis_ids)),
            "knowledge_graph_orphaned_from_analysis_history": len(set(graph_ids) - set(analysis_ids)),
        },
        "json_sample_keys": {
            "analysis_history": sorted(analysis_history[0].keys()) if analysis_history else [],
            "grading_history": sorted(grading_history[0].keys()) if grading_history else [],
            "knowledge_graph_history": sorted(graph_history[0].keys()) if graph_history else [],
        },
        "relationship_policy": (
            "Only exact existing SQLite analyses.analysis_id links are treated as relational workflow links. "
            "JSON history records without such links are preserved as standalone historical rows."
        ),
    }


def backup_sources(data_dir: Path, sqlite_path: Path) -> Path:
    backup_dir = data_dir / "migration_backups" / _now_label()
    backup_dir.mkdir(parents=True, exist_ok=False)
    candidates = [sqlite_path]
    candidates.extend(data_dir.glob("*history*.json"))
    candidates.extend(data_dir.glob("*.corrupted.json"))
    for source in candidates:
        if source.exists() and source.is_file():
            shutil.copy2(source, backup_dir / source.name)
    return backup_dir


def migrate(data_dir: Path, sqlite_path: Path) -> dict[str, Any]:
    validation = validate_sources(data_dir, sqlite_path)
    backup_dir = backup_sources(data_dir, sqlite_path)
    analysis_history = _load_json(data_dir / "analysis_history.json")
    grading_history = _load_json(data_dir / "grading_history.json")
    graph_history = _load_json(data_dir / "knowledge_graph_history.json")

    source_counts: dict[str, int] = {}
    inserted_counts: dict[str, int] = {}
    with get_session_factory()() as session:
        try:
            for model in (KnowledgeGraphRecord, GradingRecord, AnalysisHistoryRecord):
                session.execute(delete(model))
            for table in reversed(WORKFLOW_TABLES):
                session.execute(delete(sa_table(table)))

            for table in WORKFLOW_TABLES:
                rows = _sqlite_rows(sqlite_path, table)
                source_counts[table] = len(rows)
                if rows:
                    session.execute(insert(sa_table(table)), rows)

            for record in analysis_history:
                session.merge(_analysis_model(record))
            for record in grading_history:
                session.merge(_grading_model(record))
            for index, record in enumerate(graph_history):
                session.merge(_graph_model(record, index=index))
            session.flush()
            for table in WORKFLOW_TABLES:
                inserted_counts[table] = int(session.scalar(select(func.count()).select_from(sa_table(table))) or 0)
            inserted_counts["analysis_history_records"] = int(session.scalar(select(func.count()).select_from(AnalysisHistoryRecord)) or 0)
            inserted_counts["grading_records"] = int(session.scalar(select(func.count()).select_from(GradingRecord)) or 0)
            inserted_counts["knowledge_graph_records"] = int(session.scalar(select(func.count()).select_from(KnowledgeGraphRecord)) or 0)
            session.commit()
        except Exception:
            session.rollback()
            raise

    report = {
        **validation,
        "backup_dir": str(backup_dir),
        "migration_counts": {
            **{table: {"source": source_counts.get(table, 0), "postgresql": inserted_counts.get(table, 0)} for table in WORKFLOW_TABLES},
            "analysis_history_records": {"source": len(analysis_history), "postgresql": inserted_counts.get("analysis_history_records", 0)},
            "grading_records": {"source": len(grading_history), "postgresql": inserted_counts.get("grading_records", 0)},
            "knowledge_graph_records": {"source": len(graph_history), "postgresql": inserted_counts.get("knowledge_graph_records", 0)},
        },
        "notes": [
            "Historical grading and graph payloads were copied exactly; scoring/extraction was not rerun.",
            "Source SQLite and JSON files were copied to an immutable timestamped backup folder and were not deleted.",
        ],
    }
    return report


def sa_table(table_name: str) -> Any:
    from src.db.base import Base
    import src.db.models  # noqa: F401

    return Base.metadata.tables[table_name]


def write_report(report: dict[str, Any], output: Path | None) -> None:
    target = output or (DEFAULT_DATA_DIR / "migration_report.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Migration report written to {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and migrate ResearchPilot persistence to PostgreSQL.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_DATA_DIR / "researchpilot_dev.sqlite")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--migrate", action="store_true")
    args = parser.parse_args()

    if args.validate_only == args.migrate:
        raise SystemExit("Choose exactly one of --validate-only or --migrate.")
    if args.validate_only:
        write_report(validate_sources(args.data_dir, args.sqlite_path), args.output)
        return
    write_report(migrate(args.data_dir, args.sqlite_path), args.output)


if __name__ == "__main__":
    main()
