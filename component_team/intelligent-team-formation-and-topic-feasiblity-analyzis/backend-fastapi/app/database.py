import os
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

class Base(DeclarativeBase):
    pass

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False) if engine else None
_database_ready = False
_database_error = "DATABASE_URL is not configured."

def init_database() -> bool:
    global _database_ready, _database_error
    if engine is None:
        _database_ready = False
        _database_error = "DATABASE_URL is not configured. Copy .env.example to .env and set the PostgreSQL connection string."
        print(f"[database] {_database_error}")
        return False
    try:
        from app.db_models import final_allocation
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=engine)
        _database_ready = True
        _database_error = ""
        print("[database] PostgreSQL connection ready and final-allocation tables are available.")
        return True
    except Exception as exc:
        _database_ready = False
        _database_error = str(exc)
        print(f"[database] PostgreSQL initialization failed: {exc}")
        return False

def database_status() -> dict:
    return {"configured": bool(DATABASE_URL), "ready": _database_ready, "error": _database_error or None}

def get_db():
    if SessionLocal is None or not _database_ready:
        raise HTTPException(status_code=503, detail=f"Final-allocation database is not ready. {_database_error}")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
