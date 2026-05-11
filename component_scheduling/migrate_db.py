import sqlite3
conn = sqlite3.connect('schedule_drift.db')
conn.execute("""CREATE TABLE IF NOT EXISTS task_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    task_id INTEGER,
    task_name TEXT,
    assigned_to TEXT,
    effort_hours REAL,
    status TEXT DEFAULT 'NOT_STARTED',
    assigned_at TEXT,
    UNIQUE(project_id, task_id)
)""")
conn.commit()
conn.close()
print("DB migration successful - task_assignments table ready")
