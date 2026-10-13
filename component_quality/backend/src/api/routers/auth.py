from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from src.api.auth import (
    clear_session_cookie,
    get_current_supervisor,
    hash_password,
    public_supervisor_identity,
    set_session_cookie,
    verify_password,
)
from src.api.database import get_db_connection
from src.api.schemas import LoginRequest, RegisterSupervisorRequest, SupervisorIdentityResponse
from src.db import repositories

router = APIRouter(prefix="/auth", tags=["Authentication"])

DEV_LOGIN_ENABLED_ENV = "APP_ENABLE_DEV_LOGIN"
DEV_LOGIN_EMAIL_ENV = "APP_DEV_SUPERVISOR_EMAIL"
DEV_LOGIN_NAME_ENV = "APP_DEV_SUPERVISOR_NAME"
DEFAULT_DEV_SUPERVISOR_EMAIL = "dev.supervisor@researchpilot.local"
DEFAULT_DEV_SUPERVISOR_NAME = "Development Supervisor"


def _close_connection(connection: Any) -> None:
    connection.close()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(character.isalpha() for character in password):
        return "Password must include at least one letter."
    if not any(character.isdigit() for character in password):
        return "Password must include at least one number."
    return None


def _dev_login_enabled() -> bool:
    return os.getenv(DEV_LOGIN_ENABLED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


@router.post("/login", response_model=SupervisorIdentityResponse)
def login(
    payload: LoginRequest,
    response: Response,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        identity = repositories.get_supervisor_identity_by_email(connection, payload.email.strip().lower())
        if identity is None or not verify_password(payload.password, identity.get("password_hash")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        set_session_cookie(response, identity["user_id"])
        return public_supervisor_identity(identity)
    finally:
        _close_connection(connection)


@router.post("/dev-login", response_model=SupervisorIdentityResponse)
def dev_login(
    response: Response,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        if not _dev_login_enabled():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        email = _normalize_email(os.getenv(DEV_LOGIN_EMAIL_ENV, DEFAULT_DEV_SUPERVISOR_EMAIL))
        name = os.getenv(DEV_LOGIN_NAME_ENV, DEFAULT_DEV_SUPERVISOR_NAME).strip() or DEFAULT_DEV_SUPERVISOR_NAME
        identity = repositories.get_supervisor_identity_by_email(connection, email)
        if identity is None:
            identity = repositories.create_supervisor_account(
                connection,
                email=email,
                display_name=name,
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )
        set_session_cookie(response, identity["user_id"])
        return public_supervisor_identity(identity)
    finally:
        _close_connection(connection)


@router.post("/register", response_model=SupervisorIdentityResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterSupervisorRequest,
    response: Response,
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        full_name = payload.full_name.strip()
        email = _normalize_email(payload.email)
        if not full_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Full name is required.")
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid email address.")
        if payload.password != payload.confirm_password:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Passwords do not match.")
        password_error = _validate_password(payload.password)
        if password_error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=password_error)
        if repositories.get_user_by_email(connection, email) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
        try:
            identity = repositories.create_supervisor_account(
                connection,
                email=email,
                display_name=full_name,
                password_hash=hash_password(payload.password),
            )
        except IntegrityError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
        set_session_cookie(response, identity["user_id"])
        return public_supervisor_identity(identity)
    finally:
        _close_connection(connection)


@router.get("/me", response_model=SupervisorIdentityResponse)
def me(
    supervisor: dict[str, Any] = Depends(get_current_supervisor),
    connection: Any = Depends(get_db_connection),
) -> dict[str, Any]:
    try:
        return public_supervisor_identity(supervisor)
    finally:
        _close_connection(connection)


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"ok": True}
