"""Small signed-session layer for the existing IPMS role-based login.

Credentials can be replaced through IPMS_AUTH_USERS_JSON and the signing key
through IPMS_AUTH_SECRET. The browser never sends a trusted role by itself.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException


DEFAULT_USERS = {
    "supervisor1": {"password": "super@2026", "role": "supervisor", "display": "Dr. A. Perera"},
    "supervisor2": {"password": "super@2026", "role": "supervisor", "display": "Dr. B. Silva"},
    "supervisor3": {"password": "super@2026", "role": "supervisor", "display": "Dr. C. Fernando"},
    "staff1": {"password": "staff@2026", "role": "staff", "display": "Staff Member 1"},
    "staff2": {"password": "staff@2026", "role": "staff", "display": "Staff Member 2"},
}


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    display: str
    role: str


def _users() -> dict:
    configured = os.getenv("IPMS_AUTH_USERS_JSON", "").strip()
    if not configured:
        if os.getenv("IPMS_ENV", "").strip().lower() == "production":
            raise RuntimeError("Set IPMS_AUTH_USERS_JSON; demo accounts are disabled in production.")
        return DEFAULT_USERS
    try:
        users = json.loads(configured)
    except json.JSONDecodeError as exc:
        raise RuntimeError("IPMS_AUTH_USERS_JSON is not valid JSON") from exc
    if not isinstance(users, dict):
        raise RuntimeError("IPMS_AUTH_USERS_JSON must be a user-object mapping")
    return users


def _secret() -> bytes:
    configured = os.getenv("IPMS_AUTH_SECRET", "").strip()
    if os.getenv("IPMS_ENV", "").strip().lower() == "production" and len(configured) < 32:
        raise RuntimeError("Set a unique IPMS_AUTH_SECRET of at least 32 characters in production.")
    return (configured or "ipms-local-development-secret-change-me").encode("utf-8")


def authenticate(username: str, password: str, requested_role: str) -> AuthenticatedUser | None:
    record = _users().get((username or "").strip())
    if not record:
        return None
    valid = (
        hmac.compare_digest(str(record.get("password", "")), str(password or ""))
        and hmac.compare_digest(str(record.get("role", "")), str(requested_role or ""))
    )
    if not valid:
        return None
    return AuthenticatedUser(username=username.strip(), display=record.get("display", username), role=record["role"])


def issue_token(user: AuthenticatedUser, lifetime_seconds: int = 8 * 60 * 60) -> str:
    payload = {
        "sub": user.username,
        "name": user.display,
        "role": user.role,
        "exp": int(time.time()) + lifetime_seconds,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{encoded.decode()}.{encoded_signature.decode()}"


def verify_token(token: str) -> AuthenticatedUser:
    try:
        encoded, encoded_signature = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("expired")
        if payload.get("role") not in {"staff", "supervisor"}:
            raise ValueError("role")
        return AuthenticatedUser(payload["sub"], payload.get("name", payload["sub"]), payload["role"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired IPMS session.") from exc


def current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="IPMS login required.")
    return verify_token(authorization[7:].strip())


def require_roles(*allowed_roles: str):
    def dependency(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Your IPMS role cannot perform this action.")
        return user
    return dependency
