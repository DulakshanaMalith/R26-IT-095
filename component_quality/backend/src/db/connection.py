"""Explicit SQLite connection helpers for the Phase 1 data layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(database_path: str | Path) -> sqlite3.Connection:
    """Open an explicit SQLite database path with foreign keys enabled."""
    if database_path is None:
        raise ValueError("database_path is required")

    path = str(database_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
