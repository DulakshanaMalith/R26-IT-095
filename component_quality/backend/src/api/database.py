"""Database setup and request-scoped SQLite connections for data APIs."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import HTTPException, Request, status

from src.db.connection import connect
from src.db.schema import create_schema


APP_DATABASE_PATH_ENV = "APP_DATABASE_PATH"


def configured_database_path() -> Path | None:
    """Return the explicitly configured application database path, if any."""
    value = os.getenv(APP_DATABASE_PATH_ENV, "").strip()
    return Path(value) if value else None


def initialize_database(database_path: str | Path) -> None:
    """Create missing Phase 1 tables while preserving existing records."""
    connection = connect(database_path)
    try:
        create_schema(connection)
    finally:
        connection.close()


def initialize_configured_database() -> Path | None:
    """Initialize the configured SQLite database, if APP_DATABASE_PATH is set."""
    database_path = configured_database_path()
    if database_path is None:
        return None
    initialize_database(database_path)
    return database_path


def get_db_connection(request: Request) -> sqlite3.Connection:
    """Open a request-scoped SQLite connection for supervisor data APIs."""
    database_path = getattr(request.app.state, "database_path", None)
    if not database_path:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supervisor database is not configured. Set APP_DATABASE_PATH and restart the API.",
        )
    try:
        return connect(database_path)
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supervisor database is unavailable.",
        ) from exc
