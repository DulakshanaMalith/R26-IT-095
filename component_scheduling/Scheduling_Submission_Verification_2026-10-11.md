# Scheduling dissertation submission verification — 11 October 2026

This is a focused, local regression record for the dissertation. It does not
certify a production deployment, real student authentication, or improved
student outcomes.

The PostgreSQL server at `127.0.0.1:5432` was initially stopped, so the first
pytest attempt failed during test collection with `connection refused`; it was
not counted as a test result. The repository's `START_POSTGRES.bat` identifies
the local PostgreSQL data directory. After starting that server, the command
below completed successfully from the workspace root:

```powershell
$env:SCHEDULING_DATABASE_URL='postgresql://postgres@127.0.0.1:5432/ipms_scheduling_codex_test_20261010'
python -m pytest component_scheduling/test_scheduling_remediation.py -q
```

Result: **11 passed, 2 dependency deprecation warnings in 11.45 seconds**,
exit code 0, at approximately 15:34 Sri Lanka time. The warnings came from
`PyPDF2` and `pytz`, not from failed assertions. The test module refuses to
run against any database name except `ipms_scheduling_codex_test_20261010`.
The original `ipms_scheduling` database was not used as the test target.

The checks cover authenticated LPT auto-assignment, schedule versioning and
rollback, production demo-auth refusal, hall-seat rejection, History member
restoration, mixed-format deadline notices, malformed legacy History handling,
and one **synthetic local** PDF submission → supervisor approval → signed
webhook/task-progress sequence. They do not establish a new GitHub.com
delivery, full cross-component API exchange, or a real-cohort study. The
earlier detailed test evidence remains in
`Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md`.
