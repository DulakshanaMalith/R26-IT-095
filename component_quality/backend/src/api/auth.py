from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status

from src.api.database import get_db_connection
from src.db import repositories


SESSION_COOKIE_NAME = "researchpilot_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
PASSWORD_ITERATIONS = 260_000
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
AUTH_SECRET_ENV = "APP_AUTH_SECRET"


def _secret_key() -> bytes:
    secret = os.getenv(AUTH_SECRET_ENV, "").strip()
    if not secret:
        secret = "researchpilot-local-dev-auth-secret"
    return secret.encode("utf-8")


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(18)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    digest = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        prefix, iterations, salt, digest = stored_hash.split("$", 3)
        if prefix != PASSWORD_HASH_PREFIX:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        candidate = base64.urlsafe_b64encode(derived).decode("ascii")
        return hmac.compare_digest(candidate, digest)
    except (TypeError, ValueError):
        return False


def _b64_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def create_session_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    body = _b64_json(payload)
    signature = hmac.new(_secret_key(), body.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{body}.{encoded_signature}"


def verify_session_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(_secret_key(), body.encode("ascii"), hashlib.sha256).digest()
    padded_signature = signature + "=" * (-len(signature) % 4)
    try:
        supplied = base64.urlsafe_b64decode(padded_signature.encode("ascii"))
        payload = _unb64_json(body)
    except (ValueError, json.JSONDecodeError):
        return None
    if not hmac.compare_digest(supplied, expected):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None


def set_session_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user_id),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


def public_supervisor_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": identity["user_id"],
        "supervisor_id": identity["supervisor_id"],
        "email": identity["email"],
        "name": identity["display_name"],
        "role": identity["role"],
        "department": identity.get("department"),
        "title": identity.get("title"),
    }


def get_current_supervisor(
    request: Request,
    connection: sqlite3.Connection = Depends(get_db_connection),
) -> dict[str, Any]:
    user_id = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    identity = repositories.get_supervisor_identity_by_user_id(connection, user_id)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return identity
