"""SQLite storage foundation for future supervisor-centric workflows."""

from src.db.connection import connect
from src.db.schema import create_schema

__all__ = ["connect", "create_schema"]
