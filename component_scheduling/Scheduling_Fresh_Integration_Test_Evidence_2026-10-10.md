# Scheduling handoff: fresh local regression and integration evidence

Run completed on **10 October 2026 at approximately 20:48 +05:30**. The command below returned **exit code 0: 11 passed, 2 dependency deprecation warnings in 10.72 s**. The warnings came from `PyPDF2` and `pytz` and were not failed assertions.

```powershell
$env:SCHEDULING_DATABASE_URL='postgresql://postgres@127.0.0.1:5432/ipms_scheduling_codex_test_20261010'
python -m pytest component_scheduling/test_scheduling_remediation.py -q
node --check component_scheduling/frontend/script.js
python -m py_compile component_scheduling/main.py component_scheduling/postgres_db.py
```

The test module refuses to run unless the database URL names exactly `ipms_scheduling_codex_test_20261010`. Its writes were synthetic and did **not** modify the original `ipms_scheduling` database. The browser captures [11](handoff_evidence/2026-10-10/11_history_roster_version.png) and [12](handoff_evidence/2026-10-10/12_history_restored_member_ids.png) came from the same isolated test database. They show the newly generated four-task History entry and its two retained IT member IDs. They are not the earlier 25-task proposal demonstration.

The 11 checks cover the earlier six route/authentication/assignment/hall-capacity cases plus these additions:

1. A freshly generated unassigned schedule persists its exact member roster in `schedule_versions.team_members_json`, and History returns that roster when reopened.
2. An older unassigned schedule without metadata reports no member IDs; the UI requires manual IDs before Auto-Balance rather than silently allocating to `Member 1`. It cannot reconstruct unknown historical IDs.
3. The deadline checker handles flat and object-wrapped schedules, skips malformed rows and completed tasks, and creates one unread `WARNING` or `OVERDUE` notice per eligible task.
4. History does not fail wholesale when an older schedule contains a malformed task entry.
5. A **synthetic, local** document/PDF and signed-webhook flow passes through task listing, PDF upload, supervisor review queue and preview, approval, repository/identity registration, webhook HMAC validation, linked commit evidence and task-progress views.

Read-only verification of the isolated test database after the run found:

| Test group | Observed state |
|---|---|
| `CODEX-HISTORY-20261010` | Version 1 persisted `IT22101624` and `IT22109576`; browser History restored both. |
| `CODEX-FLOW-20261010` document task 1 | Submission `APPROVED`; progress `COMPLETED`, 100%, source `SUPERVISOR_REVIEW`. |
| `CODEX-FLOW-20261010` code task 2 | One synthetic commit `LINKED` to `IT22117014`; progress `IN_PROGRESS`, 10%, source `GITHUB`. |
| `CODEX-FLOW-20261010` event log | `DOCUMENT_SUBMITTED`, `DOCUMENT_APPROVED`, `GITHUB_COMMIT_RECEIVED`. |
| `CODEX-DEADLINE-20261010-*` | One `WARNING` and one `OVERDUE`; malformed fixture skipped. |

Important boundary: the webhook payload was signed locally with a **test secret** and posted through FastAPI's test client. It is not a new GitHub.com delivery, a real student authentication session, or a full cross-component production test. The document portal still uses a typed student ID and is disabled in production until verified student authentication is added. Real Team Formation group mapping and direct Quality/Risk data payloads remain unverified. No supervisor/staff usability study or real-cohort outcome measurement was conducted.
