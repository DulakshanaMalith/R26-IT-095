import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from seed_demo_data import seed_demo_data
from src.db.connection import connect


def test_seed_demo_data_is_idempotent_and_uses_local_sqlite(tmp_path):
    database_path = tmp_path / "researchpilot_dev.sqlite"

    first = seed_demo_data(database_path)
    second = seed_demo_data(database_path)

    assert first["supervisor_id"] == second["supervisor_id"]

    connection = connect(database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM supervisor_profiles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM supervisor_student_assignments").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM proposal_versions").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0
    finally:
        connection.close()
