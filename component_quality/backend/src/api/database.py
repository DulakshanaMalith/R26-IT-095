"""Database setup and request-scoped PostgreSQL connections for data APIs."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from src.db.session import DatabaseSessionAdapter, configured_database_url, get_session


DATABASE_URL_ENV = "DATABASE_URL"


def initialize_configured_database() -> str | None:
    """Record configured PostgreSQL URL; schema creation belongs to Alembic."""
    return configured_database_url()


def get_db_connection(request: Request) -> Iterator[DatabaseSessionAdapter]:
    """Open a request-scoped PostgreSQL session for data APIs."""
    database_url = getattr(request.app.state, "database_url", None)
    if not database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL database is not configured. Set DATABASE_URL and run `alembic upgrade head`.",
        )
    try:
        connection = get_session()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL database is unavailable.",
        ) from exc
    try:
        yield connection
    finally:
        connection.close()
