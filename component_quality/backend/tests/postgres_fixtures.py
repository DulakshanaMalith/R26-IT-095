from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from src.db.session import DatabaseSessionAdapter


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "").strip()
    if not value:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("TEST_DATABASE_URL="):
                    value = line.split("=", 1)[1].strip()
                    break
    if not value:
        raise RuntimeError("TEST_DATABASE_URL is required for PostgreSQL tests.")

    database_name = urlparse(value.replace("postgresql+psycopg://", "postgresql://")).path.rsplit("/", 1)[-1]
    if "test" not in database_name.lower():
        raise RuntimeError("Refusing destructive test setup: TEST_DATABASE_URL database name must contain 'test'.")
    return value


def _alembic_config() -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return config


def _reset_session_singletons() -> None:
    import src.db.session as db_session

    if db_session._engine is not None:
        db_session._engine.dispose()
    db_session._engine = None
    db_session._SessionLocal = None


def create_schema(_connection: DatabaseSessionAdapter | None = None) -> None:
    """Create a clean PostgreSQL test schema with Alembic only."""
    database_url = _test_database_url()
    os.environ["DATABASE_URL"] = database_url
    _reset_session_singletons()
    engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    command.upgrade(_alembic_config(), "head")
    _reset_session_singletons()


def connect(_database_path: object | None = None) -> DatabaseSessionAdapter:
    """Return a SQLAlchemy-backed adapter connected only to TEST_DATABASE_URL."""
    os.environ["DATABASE_URL"] = _test_database_url()
    _reset_session_singletons()
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    return DatabaseSessionAdapter(__import__("sqlalchemy.orm").orm.Session(bind=engine, expire_on_commit=False))
