"""Shared local secret for component-to-component submission traffic."""
from __future__ import annotations

import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / ".runtime"
SECRET_FILE = RUNTIME_DIR / "submission_integration.key"


def submission_integration_key() -> str:
    """Use an environment secret, or create a persistent local-only secret."""
    configured = os.getenv("IPMS_SUBMISSION_INTEGRATION_KEY", "").strip()
    if configured:
        return configured
    if os.getenv("IPMS_ENV", "").strip().lower() == "production":
        raise RuntimeError("Set IPMS_SUBMISSION_INTEGRATION_KEY in production.")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.is_file():
        value = SECRET_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(value, encoding="utf-8")
    return value
