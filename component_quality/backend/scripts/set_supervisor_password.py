"""Set a local supervisor login password without seeding student data."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.auth import hash_password
from src.db.session import get_session
from src.db.repositories import create_supervisor_profile, create_user, get_supervisor_profile_by_user_id, get_user_by_email, update_user_password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Set a local supervisor login password.")
    parser.add_argument("--email", required=True, help="Supervisor email address.")
    parser.add_argument("--name", default="Local Supervisor", help="Supervisor display name when creating the account.")
    args = parser.parse_args()

    password = getpass.getpass("Supervisor password: ")
    confirm = getpass.getpass("Confirm supervisor password: ")
    if not password or password != confirm:
        raise SystemExit("Passwords were empty or did not match.")

    connection = get_session()
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
        print("Supervisor password updated in PostgreSQL.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
