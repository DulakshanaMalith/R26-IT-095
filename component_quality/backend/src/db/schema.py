"""SQLite schema for supervisor-owned proposal/version workflows."""

from __future__ import annotations

import sqlite3


def create_schema(connection: sqlite3.Connection) -> None:
    """Create Phase 1 tables without touching production JSON history."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            role TEXT NOT NULL CHECK (role IN ('supervisor', 'admin', 'panel')),
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS supervisor_profiles (
            supervisor_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL UNIQUE,
            department TEXT,
            title TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            academic_student_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            program TEXT,
            cohort TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS supervisor_student_assignments (
            assignment_id TEXT PRIMARY KEY,
            supervisor_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            assignment_role TEXT NOT NULL CHECK (assignment_role IN ('primary_supervisor', 'co_supervisor')),
            assigned_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            FOREIGN KEY (supervisor_id) REFERENCES supervisor_profiles(supervisor_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_supervisor_student_role
            ON supervisor_student_assignments(supervisor_id, student_id, assignment_role)
            WHERE active = 1;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_primary_supervisor_per_student
            ON supervisor_student_assignments(student_id)
            WHERE active = 1 AND assignment_role = 'primary_supervisor';

        CREATE TABLE IF NOT EXISTS proposals (
            proposal_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE TABLE IF NOT EXISTS proposal_versions (
            version_id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            original_filename TEXT,
            source_type TEXT,
            original_file_path TEXT,
            extracted_text TEXT,
            edited_text TEXT,
            created_at TEXT NOT NULL,
            submitted_at TEXT,
            status TEXT NOT NULL,
            UNIQUE (proposal_id, version_number),
            UNIQUE (version_id, proposal_id),
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
        );

        CREATE TABLE IF NOT EXISTS analyses (
            analysis_id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            request_id TEXT,
            created_at TEXT NOT NULL,
            source TEXT,
            input_text_snapshot TEXT,
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
            FOREIGN KEY (version_id, proposal_id) REFERENCES proposal_versions(version_id, proposal_id)
        );

        CREATE TABLE IF NOT EXISTS supervisor_reviews (
            review_id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            supervisor_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (decision IN ('SEND_FEEDBACK', 'REVISION_REQUESTED', 'READY_FOR_PANEL', 'REVIEWED')),
            overall_comment TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
            FOREIGN KEY (version_id, proposal_id) REFERENCES proposal_versions(version_id, proposal_id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisor_profiles(supervisor_id)
        );

        CREATE TABLE IF NOT EXISTS ai_supervisor_review_drafts (
            draft_id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            analysis_id TEXT NOT NULL,
            draft_json TEXT NOT NULL,
            evidence_json TEXT,
            llm_metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (version_id, analysis_id),
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
            FOREIGN KEY (version_id, proposal_id) REFERENCES proposal_versions(version_id, proposal_id),
            FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
        );

        CREATE TABLE IF NOT EXISTS supervisor_review_drafts (
            review_id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL,
            analysis_id TEXT NOT NULL,
            supervisor_id TEXT NOT NULL,
            ai_draft_id TEXT NOT NULL,
            overall_assessment TEXT NOT NULL,
            strengths_json TEXT NOT NULL,
            areas_requiring_improvement_json TEXT NOT NULL,
            methodology_feedback TEXT NOT NULL,
            evaluation_validation_feedback TEXT NOT NULL,
            recommendations_json TEXT NOT NULL,
            suggested_revision_instructions_json TEXT NOT NULL,
            supervisor_comments TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (supervisor_id, version_id, analysis_id),
            FOREIGN KEY (version_id) REFERENCES proposal_versions(version_id),
            FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisor_profiles(supervisor_id),
            FOREIGN KEY (ai_draft_id) REFERENCES ai_supervisor_review_drafts(draft_id)
        );

        CREATE TABLE IF NOT EXISTS notification_logs (
            notification_id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            version_id TEXT,
            analysis_id TEXT,
            supervisor_id TEXT,
            supervisor_review_draft_id TEXT,
            review_id TEXT,
            recipient_email TEXT,
            subject TEXT,
            notification_type TEXT NOT NULL CHECK (notification_type IN ('FEEDBACK_SENT', 'REVISION_REQUESTED', 'READY_FOR_PANEL')),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent_at TEXT,
            error_message TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
            FOREIGN KEY (version_id) REFERENCES proposal_versions(version_id),
            FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id),
            FOREIGN KEY (supervisor_id) REFERENCES supervisor_profiles(supervisor_id),
            FOREIGN KEY (supervisor_review_draft_id) REFERENCES supervisor_review_drafts(review_id),
            FOREIGN KEY (review_id) REFERENCES supervisor_reviews(review_id)
        );
        """
    )
    _ensure_notification_log_columns(connection)
    connection.commit()


def _ensure_notification_log_columns(connection: sqlite3.Connection) -> None:
    """Add Step 8 delivery-tracking columns without resetting existing data."""
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(notification_logs)").fetchall()
    }
    columns = {
        "analysis_id": "TEXT",
        "supervisor_id": "TEXT",
        "supervisor_review_draft_id": "TEXT",
        "subject": "TEXT",
    }
    for name, definition in columns.items():
        if name not in existing_columns:
            connection.execute(f"ALTER TABLE notification_logs ADD COLUMN {name} {definition}")
