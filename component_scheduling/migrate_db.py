"""One-time migration of legacy scheduling data from SQLite to PostgreSQL.

Set SCHEDULING_DATABASE_URL if PostgreSQL is not using the default local URL.
Existing PostgreSQL rows are preserved; conflicts are skipped.
"""

from __future__ import annotations

import argparse
import os
import sqlite3

import postgres_db


TABLES = (
    "schedule_versions", "sentiment_log", "cross_project_edges",
    "task_submissions", "notifications", "github_registrations",
    "task_progress", "progress_events", "project_reviewers",
    "student_github_identities", "github_webhook_deliveries", "github_commits",
    "github_pull_requests",
    "task_assignments", "task_assignment_history", "current_project",
    "supervisors", "halls", "academic_schedule_batches", "academic_events",
    "staff_availability", "hall_availability", "event_panel_members",
    "academic_event_audit",
)


def migrate(source_path: str) -> dict[str, int]:
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Legacy SQLite database not found: {source_path}")

    postgres_db.initialize_schema()
    source = sqlite3.connect(source_path)
    target = postgres_db.connect()
    migrated: dict[str, int] = {}
    try:
        target_cursor = target.cursor()
        for table in TABLES:
            exists = source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                migrated[table] = 0
                continue

            source_columns = [
                row[1] for row in source.execute(f'PRAGMA table_info("{table}")').fetchall()
            ]
            target_cursor.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name=? ORDER BY ordinal_position""",
                (table,),
            )
            target_columns = {row[0] for row in target_cursor.fetchall()}
            columns = [column for column in source_columns if column in target_columns]
            if not columns:
                migrated[table] = 0
                continue

            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            source_rows = source.execute(
                f'SELECT {quoted_columns} FROM "{table}"'
            ).fetchall()
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = (
                f'INSERT INTO "{table}" ({quoted_columns}) '
                f'VALUES ({placeholders}) ON CONFLICT DO NOTHING'
            )
            for row in source_rows:
                target_cursor.execute(insert_sql, row)
            migrated[table] = len(source_rows)

            if "id" in columns:
                target_cursor.execute(
                    f"""SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM \"{table}\"), 1),
                        EXISTS(SELECT 1 FROM \"{table}\")
                    )"""
                )

        target.commit()
        return migrated
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=os.path.join(os.path.dirname(__file__), "schedule_drift.db"),
        help="Path to the legacy SQLite database",
    )
    args = parser.parse_args()
    migrated = migrate(os.path.abspath(args.source))
    print("SQLite to PostgreSQL migration completed:")
    for table, count in migrated.items():
        print(f"  {table}: {count} source row(s) processed")


if __name__ == "__main__":
    main()
