"""Set a local supervisor login password without seeding student data."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.auth import hash_password
from src.db.connection import connect
from src.db.repositories import create_supervisor_profile, create_user, get_supervisor_profile_by_user_id, get_user_by_email, update_user_password_hash


def _resolve_database_path(args: argparse.Namespace) -> str:
    database_path = args.database or os.getenv("APP_DATABASE_PATH")
    if not database_path:
        raise SystemExit("Set APP_DATABASE_PATH or pass --database for the local development SQLite file.")
    return database_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Set a local supervisor login password.")
    parser.add_argument("--database", help="SQLite database path. Defaults to APP_DATABASE_PATH.")
    parser.add_argument("--email", required=True, help="Supervisor email address.")
    parser.add_argument("--name", default="Local Supervisor", help="Supervisor display name when creating the account.")
    args = parser.parse_args()

    password = getpass.getpass("Supervisor password: ")
    confirm = getpass.getpass("Confirm supervisor password: ")
    if not password or password != confirm:
        raise SystemExit("Passwords were empty or did not match.")

    connection = connect(_resolve_database_path(args))
    try:
        email = args.email.strip().lower()
        user = get_user_by_email(connection, email)
        if user is None:
            user = create_user(connection, email=email, role="supervisor", display_name=args.name)
        if user["role"] != "supervisor":
            raise SystemExit("User exists but is not a supervisor.")
        if get_supervisor_profile_by_user_id(connection, user["user_id"]) is None:
            create_supervisor_profile(connection, user_id=user["user_id"], department="Computing", title="Dr.")
        update_user_password_hash(connection, user_id=user["user_id"], password_hash=hash_password(password))
        print("Supervisor password updated.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
