"""PostgreSQL database adapter for the scheduling component.

The adapter keeps the small DB-API surface used by the existing FastAPI routes
while translating their legacy qmark placeholders to psycopg2 placeholders.
No application data is written to SQLite.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

import psycopg2
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)


DEFAULT_DATABASE_URL = "postgresql://postgres@127.0.0.1:5432/ipms_scheduling"

SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS schedule_versions (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL,
        schedule_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """ALTER TABLE schedule_versions ADD COLUMN IF NOT EXISTS team_members_json TEXT""",
    """CREATE INDEX IF NOT EXISTS idx_schedule_versions_project
        ON schedule_versions(project_id, version DESC)""",
    """CREATE TABLE IF NOT EXISTS sentiment_log (
        id BIGSERIAL PRIMARY KEY, project_id TEXT, message TEXT, score DOUBLE PRECISION,
        label TEXT, timestamp TEXT)""",
    """CREATE TABLE IF NOT EXISTS cross_project_edges (
        id BIGSERIAL PRIMARY KEY, from_task TEXT, to_task TEXT, dependency_type TEXT)""",
    """CREATE TABLE IF NOT EXISTS task_submissions (
        id BIGSERIAL PRIMARY KEY, project_id TEXT, task_id INTEGER, filename TEXT,
        submitted_at TEXT, status TEXT DEFAULT 'SUBMITTED')""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS task_key TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS student_id TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS submission_version INTEGER NOT NULL DEFAULT 1""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS original_filename TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS stored_filename TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS storage_path TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS mime_type TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS file_size BIGINT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS sha256_hash TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS reviewer_id TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS review_comments TEXT""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ""",
    """ALTER TABLE task_submissions ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT FALSE""",
    """CREATE INDEX IF NOT EXISTS idx_task_submissions_review
        ON task_submissions(project_id, review_status, submitted_at DESC)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_task_submission_hash_version
        ON task_submissions(project_id, task_id, sha256_hash, submission_version)
        WHERE sha256_hash IS NOT NULL""",
    """CREATE TABLE IF NOT EXISTS task_progress (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, task_id BIGINT NOT NULL,
        task_key TEXT NOT NULL, assigned_member_id TEXT, status TEXT NOT NULL DEFAULT 'NOT_STARTED',
        progress_percentage DOUBLE PRECISION NOT NULL DEFAULT 0,
        progress_source TEXT NOT NULL DEFAULT 'SYSTEM', last_activity_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_by TEXT,
        UNIQUE(project_id, task_id), CHECK(progress_percentage >= 0 AND progress_percentage <= 100))""",
    """CREATE INDEX IF NOT EXISTS idx_task_progress_project
        ON task_progress(project_id, status, updated_at DESC)""",
    """CREATE TABLE IF NOT EXISTS progress_events (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, task_id BIGINT NOT NULL,
        task_key TEXT NOT NULL, event_type TEXT NOT NULL, source TEXT NOT NULL,
        actor_id TEXT, evidence_id TEXT, previous_progress DOUBLE PRECISION,
        new_progress DOUBLE PRECISION, metadata_json TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE INDEX IF NOT EXISTS idx_progress_events_task
        ON progress_events(project_id, task_id, created_at DESC)""",
    """CREATE TABLE IF NOT EXISTS project_reviewers (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, reviewer_username TEXT NOT NULL,
        assigned_by TEXT NOT NULL, assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(project_id, reviewer_username))""",
    """CREATE TABLE IF NOT EXISTS notifications (
        id BIGSERIAL PRIMARY KEY, project_id TEXT, task_id INTEGER, task_name TEXT,
        type TEXT, message TEXT, created_at TEXT, is_read INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS github_registrations (
        id BIGSERIAL PRIMARY KEY, project_id TEXT, repo_url TEXT, registered_at TEXT)""",
    """ALTER TABLE github_registrations ADD COLUMN IF NOT EXISTS repository_full_name TEXT""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_github_repository_full_name
        ON github_registrations(repository_full_name) WHERE repository_full_name IS NOT NULL""",
    """CREATE TABLE IF NOT EXISTS student_github_identities (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, student_id TEXT NOT NULL,
        github_login TEXT NOT NULL, registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(project_id, student_id), UNIQUE(project_id, github_login))""",
    """CREATE TABLE IF NOT EXISTS github_webhook_deliveries (
        id BIGSERIAL PRIMARY KEY, delivery_id TEXT NOT NULL UNIQUE,
        repository_full_name TEXT, event_type TEXT NOT NULL,
        received_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS github_commits (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, repository_full_name TEXT NOT NULL,
        commit_sha TEXT NOT NULL, author_login TEXT, author_email TEXT, message TEXT,
        branch TEXT, task_id BIGINT, task_key TEXT, linked_student_id TEXT,
        evidence_status TEXT NOT NULL DEFAULT 'RECORDED', committed_at TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(repository_full_name, commit_sha))""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS project_id TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS repository_full_name TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS commit_sha TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS author_login TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS author_email TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS message TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS branch TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS task_id BIGINT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS task_key TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS linked_student_id TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS evidence_status TEXT DEFAULT 'RECORDED'""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS committed_at TEXT""",
    """ALTER TABLE github_commits ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_github_commit_sha
        ON github_commits(repository_full_name, commit_sha)
        WHERE repository_full_name IS NOT NULL AND commit_sha IS NOT NULL""",
    """CREATE INDEX IF NOT EXISTS idx_github_commits_task
        ON github_commits(project_id, task_id, created_at DESC)""",
    """CREATE TABLE IF NOT EXISTS github_pull_requests (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL,
        repository_full_name TEXT NOT NULL, pull_number INTEGER NOT NULL,
        task_id BIGINT, task_key TEXT, author_login TEXT, linked_student_id TEXT,
        title TEXT, branch TEXT, html_url TEXT, state TEXT,
        review_status TEXT NOT NULL DEFAULT 'PENDING', evidence_status TEXT NOT NULL DEFAULT 'RECORDED',
        merged BOOLEAN NOT NULL DEFAULT FALSE,
        opened_at TEXT, updated_at TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(repository_full_name, pull_number))""",
    """ALTER TABLE github_pull_requests ADD COLUMN IF NOT EXISTS evidence_status TEXT NOT NULL DEFAULT 'RECORDED'""",
    """CREATE INDEX IF NOT EXISTS idx_github_pull_requests_task
        ON github_pull_requests(project_id, task_id, updated_at DESC)""",
    """CREATE TABLE IF NOT EXISTS task_assignments (
        id BIGSERIAL PRIMARY KEY, project_id TEXT NOT NULL, task_id INTEGER NOT NULL,
        task_name TEXT, assigned_to TEXT, effort_hours DOUBLE PRECISION,
        status TEXT DEFAULT 'NOT_STARTED', assigned_at TEXT,
        UNIQUE(project_id, task_id))""",
    """CREATE INDEX IF NOT EXISTS idx_task_assignments_project_member
        ON task_assignments(project_id, assigned_to, status)""",
    """CREATE TABLE IF NOT EXISTS task_assignment_history (
        id BIGSERIAL PRIMARY KEY, project_id TEXT, task_id INTEGER,
        from_member TEXT, to_member TEXT, method TEXT, reason TEXT,
        created_at TEXT, approved_by TEXT)""",
    """CREATE TABLE IF NOT EXISTS current_project (
        id BIGSERIAL PRIMARY KEY, group_id TEXT, research_topic TEXT,
        supervisor_name TEXT, description_snippet TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS supervisors (
        id BIGSERIAL PRIMARY KEY, name TEXT, email TEXT, expertise TEXT,
        available_dates TEXT, available_times TEXT,
        role TEXT DEFAULT 'Professor', uploaded_at TEXT)""",
    """ALTER TABLE supervisors ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE""",
    """CREATE TABLE IF NOT EXISTS halls (
        id BIGSERIAL PRIMARY KEY, hall_name TEXT, capacity INTEGER,
        floor_building TEXT, available_dates TEXT, available_times TEXT,
        uploaded_at TEXT)""",
    """ALTER TABLE halls ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE""",
    """CREATE TABLE IF NOT EXISTS academic_events (
        id BIGSERIAL PRIMARY KEY, event_type TEXT, group_id TEXT, group_topic TEXT,
        supervisor_id INTEGER, supervisor_name TEXT, match_score DOUBLE PRECISION,
        hall_id INTEGER, hall_name TEXT, scheduled_date TEXT, scheduled_time TEXT,
        duration_minutes INTEGER DEFAULT 60, status TEXT DEFAULT 'Scheduled',
        notes TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS viva_progress_snapshots (
        id BIGSERIAL PRIMARY KEY, event_id BIGINT NOT NULL UNIQUE,
        project_id TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        captured_by TEXT NOT NULL, captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS academic_schedule_batches (
        id BIGSERIAL PRIMARY KEY, version INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'DRAFT', start_date DATE NOT NULL,
        configuration_json TEXT NOT NULL, created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), published_by TEXT,
        published_at TIMESTAMPTZ, UNIQUE(version))""",
    """ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS batch_id BIGINT
        REFERENCES academic_schedule_batches(id) ON DELETE CASCADE""",
    """ALTER TABLE academic_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ""",
    """ALTER TABLE academic_events ALTER COLUMN updated_at SET DEFAULT NOW()""",
    """CREATE INDEX IF NOT EXISTS idx_academic_events_batch
        ON academic_events(batch_id, scheduled_date, scheduled_time)""",
    """CREATE TABLE IF NOT EXISTS academic_event_audit (
        id BIGSERIAL PRIMARY KEY, event_id BIGINT, batch_id BIGINT,
        action TEXT NOT NULL, actor TEXT NOT NULL, before_json TEXT,
        after_json TEXT, reason TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""",
    """CREATE TABLE IF NOT EXISTS staff_availability (
        id BIGSERIAL PRIMARY KEY, supervisor_id BIGINT NOT NULL REFERENCES supervisors(id) ON DELETE CASCADE,
        available_date DATE NOT NULL, start_time TIME NOT NULL, end_time TIME NOT NULL,
        is_available BOOLEAN NOT NULL DEFAULT TRUE,
        UNIQUE(supervisor_id, available_date, start_time, end_time))""",
    """CREATE TABLE IF NOT EXISTS hall_availability (
        id BIGSERIAL PRIMARY KEY, hall_id BIGINT NOT NULL REFERENCES halls(id) ON DELETE CASCADE,
        available_date DATE NOT NULL, start_time TIME NOT NULL, end_time TIME NOT NULL,
        is_available BOOLEAN NOT NULL DEFAULT TRUE,
        UNIQUE(hall_id, available_date, start_time, end_time))""",
    """CREATE TABLE IF NOT EXISTS event_panel_members (
        id BIGSERIAL PRIMARY KEY, event_id BIGINT REFERENCES academic_events(id) ON DELETE CASCADE,
        member_name TEXT, member_role TEXT, member_email TEXT)""",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_academic_one_published
        ON academic_schedule_batches ((status)) WHERE status='PUBLISHED'""",
    """CREATE INDEX IF NOT EXISTS idx_academic_audit_batch
        ON academic_event_audit(batch_id, created_at DESC)""",
)


def database_url() -> str:
    return os.getenv("SCHEDULING_DATABASE_URL", DEFAULT_DATABASE_URL).strip()


def _translate_qmark(sql: str) -> str:
    """Translate SQLite-style ? parameters without touching quoted literals."""
    output: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    translated = "".join(output)
    translated = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGSERIAL PRIMARY KEY",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r'\bDEFAULT\s+"([A-Za-z0-9_ -]+)"',
        lambda match: "DEFAULT '" + match.group(1).replace("'", "''") + "'",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r"ALTER\s+TABLE\s+supervisors\s+ADD\s+COLUMN\s+(?!IF\s+NOT\s+EXISTS)",
        "ALTER TABLE supervisors ADD COLUMN IF NOT EXISTS ",
        translated,
        flags=re.IGNORECASE,
    )
    return translated


class PostgresCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid: int | None = None

    def execute(self, sql: str, params: Iterable[Any] | None = None):
        statement = _translate_qmark(sql)
        needs_event_id = (
            statement.lstrip().upper().startswith("INSERT INTO ACADEMIC_EVENTS")
            and "RETURNING" not in statement.upper()
        )
        if needs_event_id:
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
        self._cursor.execute(statement, tuple(params or ()))
        if needs_event_id:
            self._lastrowid = int(self._cursor.fetchone()[0])
        return self

    def executemany(self, sql: str, params_seq):
        self._cursor.executemany(_translate_qmark(sql), params_seq)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return self._lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._connection.cursor())

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> PostgresCursor:
        return self.cursor().execute(sql, params)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def connect(_legacy_path: str | None = None) -> PostgresConnection:
    """Connect exclusively to the configured PostgreSQL scheduling database."""
    return PostgresConnection(psycopg2.connect(database_url(), connect_timeout=10))


def initialize_schema() -> None:
    """Create or upgrade the PostgreSQL scheduling schema idempotently."""
    connection = connect()
    try:
        cursor = connection.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
