from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL_ENV = "DATABASE_URL"
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"


def configured_database_url() -> str | None:
    """Return the configured PostgreSQL URL."""
    value = os.getenv(DATABASE_URL_ENV, "").strip()
    return value or None


def require_database_url() -> str:
    """Return DATABASE_URL or fail with an operationally clear message."""
    value = configured_database_url()
    if not value:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL persistence.")
    return value


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create the PostgreSQL engine lazily from DATABASE_URL."""
    global _engine
    if _engine is None:
        _engine = create_engine(require_database_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Create the session factory lazily so imports do not require env setup."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False)
    return _SessionLocal


class _CompatRow(dict):
    def __init__(self, mapping: Any):
        super().__init__(mapping)
        self._values = list(mapping.values())

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class _RowResult:
    def __init__(self, result: Result[Any]):
        self._result = result
        self.rowcount = result.rowcount

    def __iter__(self):
        return iter(self.fetchall())

    def fetchone(self) -> dict[str, Any] | None:
        row = self._result.mappings().first()
        return _CompatRow(row) if row is not None else None

    def fetchall(self) -> list[dict[str, Any]]:
        return [_CompatRow(row) for row in self._result.mappings().all()]


class DatabaseSessionAdapter:
    """Expose a DB-API-like surface backed by a SQLAlchemy Session.

    The existing repositories are intentionally small SQL helpers. This adapter
    lets those call sites move to PostgreSQL while their SQL is incrementally
    normalized to SQLAlchemy.
    """

    def __init__(self, session: Session):
        self.session = session

    def execute(self, query: str, params: tuple[Any, ...] | dict[str, Any] = ()) -> _RowResult:
        normalized = query.strip()
        if normalized.upper() in {"BEGIN", "BEGIN IMMEDIATE"}:
            return _RowResult(self.session.execute(text("SELECT 1 WHERE false")))
        if normalized.upper().startswith("PRAGMA "):
            return _RowResult(self.session.execute(text("SELECT 1 WHERE false")))

        statement, bound = _convert_sqlite_placeholders(query, params)
        return _RowResult(self.session.execute(text(statement), bound))

    def executescript(self, _script: str) -> None:
        raise RuntimeError("Runtime schema creation is disabled. Run `alembic upgrade head`.")

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()


def _convert_sqlite_placeholders(query: str, params: tuple[Any, ...] | dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if isinstance(params, dict):
        return query, params
    values = list(params)
    index = 0
    bound: dict[str, Any] = {}

    def replace(_match: re.Match[str]) -> str:
        nonlocal index
        key = f"p{index}"
        bound[key] = values[index]
        index += 1
        return f":{key}"

    statement = re.sub(r"\?", replace, query)
    return statement, bound


def get_session() -> DatabaseSessionAdapter:
    """Open a SQLAlchemy-backed repository adapter."""
    return DatabaseSessionAdapter(get_session_factory()())


@contextmanager
def session_scope() -> Iterator[DatabaseSessionAdapter]:
    """Provide a transaction-capable adapter for scripts and services."""
    adapter = get_session()
    try:
        yield adapter
        adapter.commit()
    except SQLAlchemyError:
        adapter.rollback()
        raise
    finally:
        adapter.close()
