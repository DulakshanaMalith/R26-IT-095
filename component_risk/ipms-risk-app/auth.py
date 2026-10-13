"""Password hashing, login sessions and role-based access checks."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

import database

SESSION_COOKIE = "ipms_session"
SESSION_DAYS = 7
PBKDF2_ITERATIONS = 200_000
ROLES = ("student", "supervisor")


def hash_password(password, salt=None):
    """Returns (hash_hex, salt_hex). PBKDF2-HMAC-SHA256 with a random salt."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return digest.hex(), salt


def verify_password(password, password_hash, salt):
    candidate, _ = hash_password(password, salt)
    # Constant-time comparison to avoid timing attacks.
    return hmac.compare_digest(candidate, password_hash)


def validate_registration(email, full_name, password, role):
    """Returns an error message, or None when the input is acceptable."""
    if not full_name.strip():
        return "Full name is required."
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if role not in ROLES:
        return "Select a valid role."
    if database.get_user_by_email(email):
        return "An account with that email already exists."
    return None


def register_user(email, full_name, password, role):
    password_hash, salt = hash_password(password)
    return database.create_user(email, full_name, password_hash, salt, role)


def login(email, password):
    """Returns (session_token, error). Token is None when login fails."""
    user = database.get_user_by_email(email)

    if user is None or not verify_password(password, user["password_hash"], user["salt"]):
        # Same message either way so accounts cannot be enumerated.
        return None, "Incorrect email or password."

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")
    database.create_session(token, user["id"], expires_at)
    return token, None


def logout(token):
    if token:
        database.delete_session(token)


def current_user(request):
    """The logged-in user for this request, or None."""
    return database.get_session_user(request.cookies.get(SESSION_COOKIE))


def set_session_cookie(response, token):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax"
    )


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE)


# --------------------------------------------------------- access control

def can_access_project(user, project):
    """Supervisors see projects they supervise; students see projects they belong to."""
    if user is None or project is None:
        return False

    if user["role"] == "supervisor":
        return project["supervisor_id"] == user["id"]

    return database.is_member(project["id"], user["id"])


def visible_projects(user):
    if user is None:
        return []

    if user["role"] == "supervisor":
        return database.list_projects_for_supervisor(user["id"])

    return database.list_projects_for_student(user["id"])


def resolve_project(user, project_id):
    """Loads a project only if this user is allowed to see it."""
    if not project_id:
        return None

    project = database.get_project(project_id)
    return project if can_access_project(user, project) else None
