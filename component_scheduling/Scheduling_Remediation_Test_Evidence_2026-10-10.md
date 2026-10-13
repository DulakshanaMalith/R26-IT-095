# Scheduling remediation — focused test evidence

Run recorded: **2026-10-10 18:33:51 +05:30** (Asia/Colombo). Working directory: `D:\New folder (91)`. Target database: the isolated PostgreSQL database `ipms_scheduling_codex_test_20261010`; no production database was used.

```powershell
$env:SCHEDULING_DATABASE_URL='postgresql://postgres@127.0.0.1:5432/ipms_scheduling_codex_test_20261010'
python -m pytest component_scheduling/test_scheduling_remediation.py -q
```

Result: **exit code 0; 6 passed, 2 warnings in 10.40s**. The two warnings were dependency deprecations in `pytz` and `PyPDF2`, not test failures.

The six tests cover unique/login-protected auto-assignment routing; production refusal of demo credentials; balanced schedule version and ownership persistence with stale/repeated request rejection; the hall-seat calculation; invalid seat-policy rejection; and undersized-hall rejection during draft scheduling, rescheduling and publication. The suite is intentionally limited to these repaired paths. It does **not** demonstrate real-student assignment quality, a complete document/GitHub journey, or live Team Formation, Quality or Risk payload exchange.

Source: `test_scheduling_remediation.py`. The module skips if `SCHEDULING_DATABASE_URL` does not name the exact isolated test database above; this protects other databases from its synthetic writes.
