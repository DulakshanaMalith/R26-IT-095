"""SQLite storage for users, projects, team membership and login sessions."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "ipms.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE NOT NULL,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student', 'supervisor')),
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    team_id          TEXT NOT NULL,
    github_url       TEXT NOT NULL DEFAULT '',
    jira_project_key TEXT NOT NULL DEFAULT '',
    supervisor_id    INTEGER NOT NULL REFERENCES users(id),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id   INTEGER NOT NULL REFERENCES projects(id),
    user_id      INTEGER NOT NULL REFERENCES users(id),
    github_login TEXT NOT NULL DEFAULT '',
    jira_name    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    risk_status TEXT NOT NULL,
    recipients  TEXT NOT NULL,
    sent_at     TEXT NOT NULL
);
"""


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with connect() as connection:
        connection.executescript(SCHEMA)

        # Migration for databases created before automatic risk emails.
        try:
            connection.execute(
                "ALTER TABLE projects ADD COLUMN last_risk_status TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass  # column already exists


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- users

def create_user(email, full_name, password_hash, salt, role):
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO users (email, full_name, password_hash, salt, role, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email.strip().lower(), full_name.strip(), password_hash, salt, role, now_iso())
        )
        return cursor.lastrowid


def get_user_by_email(email):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()


def get_user_by_id(user_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def list_students():
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE role = 'student' ORDER BY full_name"
        ).fetchall()


# ------------------------------------------------------------- sessions

def create_session(token, user_id, expires_at):
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now_iso(), expires_at)
        )


def get_session_user(token):
    """Returns the user row for a valid, unexpired session token."""
    if not token:
        return None

    with connect() as connection:
        row = connection.execute(
            """SELECT users.*, sessions.expires_at
                 FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?""",
            (token,)
        ).fetchone()

    if row is None:
        return None

    if row["expires_at"] < now_iso():
        delete_session(token)
        return None

    return row


def delete_session(token):
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))


# ------------------------------------------------------------- projects

def create_project(name, team_id, github_url, jira_project_key, supervisor_id):
    with connect() as connection:
        cursor = connection.execute(
            """INSERT INTO projects
               (name, team_id, github_url, jira_project_key, supervisor_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name.strip(), team_id.strip(), github_url.strip(),
             jira_project_key.strip(), supervisor_id, now_iso())
        )
        return cursor.lastrowid


def get_project(project_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()


def update_project(project_id, name, team_id, github_url, jira_project_key):
    with connect() as connection:
        connection.execute(
            """UPDATE projects
                  SET name = ?, team_id = ?, github_url = ?, jira_project_key = ?
                WHERE id = ?""",
            (name.strip(), team_id.strip(), github_url.strip(),
             jira_project_key.strip(), project_id)
        )


def list_projects_for_supervisor(supervisor_id):
    with connect() as connection:
        return connection.execute(
            """SELECT projects.*,
                      (SELECT COUNT(*) FROM project_members
                        WHERE project_members.project_id = projects.id) AS member_count
                 FROM projects WHERE supervisor_id = ? ORDER BY created_at DESC""",
            (supervisor_id,)
        ).fetchall()


def list_projects_for_student(user_id):
    with connect() as connection:
        return connection.execute(
            """SELECT projects.*,
                      (SELECT COUNT(*) FROM project_members
                        WHERE project_members.project_id = projects.id) AS member_count
                 FROM projects
                 JOIN project_members ON project_members.project_id = projects.id
                WHERE project_members.user_id = ? ORDER BY projects.created_at DESC""",
            (user_id,)
        ).fetchall()


# -------------------------------------------------------- team membership

def add_member(project_id, user_id, github_login="", jira_name=""):
    with connect() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO project_members
               (project_id, user_id, github_login, jira_name) VALUES (?, ?, ?, ?)""",
            (project_id, user_id, github_login.strip(), jira_name.strip())
        )


def remove_member(project_id, user_id):
    with connect() as connection:
        connection.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id)
        )


def list_members(project_id):
    with connect() as connection:
        return connection.execute(
            """SELECT users.id, users.full_name, users.email,
                      project_members.github_login, project_members.jira_name
                 FROM project_members JOIN users ON users.id = project_members.user_id
                WHERE project_members.project_id = ? ORDER BY users.full_name""",
            (project_id,)
        ).fetchall()


def is_member(project_id, user_id):
    with connect() as connection:
        return connection.execute(
            "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id)
        ).fetchone() is not None


# ------------------------------------------------------------ risk alerts

def list_projects_with_repo():
    """Projects the background monitor should check (those with a repo set)."""
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM projects WHERE github_url != '' ORDER BY id"
        ).fetchall()


def set_project_risk_status(project_id, risk_status):
    with connect() as connection:
        connection.execute(
            "UPDATE projects SET last_risk_status = ? WHERE id = ?",
            (risk_status, project_id)
        )


def get_last_alert(project_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM risk_alerts WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,)
        ).fetchone()


def record_alert(project_id, risk_status, recipients):
    with connect() as connection:
        connection.execute(
            """INSERT INTO risk_alerts (project_id, risk_status, recipients, sent_at)
               VALUES (?, ?, ?, ?)""",
            (project_id, risk_status, recipients, now_iso())
        )


def list_alert_recipients(project_id):
    """Email addresses of everyone who should hear about a risk alert:
    all team members plus the supervisor."""
    with connect() as connection:
        rows = connection.execute(
            """SELECT users.email FROM project_members
                 JOIN users ON users.id = project_members.user_id
                WHERE project_members.project_id = ?
               UNION
               SELECT users.email FROM projects
                 JOIN users ON users.id = projects.supervisor_id
                WHERE projects.id = ?""",
            (project_id, project_id)
        ).fetchall()

    return [row["email"] for row in rows]
