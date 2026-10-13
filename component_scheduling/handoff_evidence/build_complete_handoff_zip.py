"""Build a curated common-report handoff ZIP without private env secrets.

The allowlist intentionally excludes .env files, database exports, uploaded
student documents, raw datasets and temporary runtime files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


COMPONENT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__file__).resolve().parent / "Scheduling_Complete_Component_Handoff_2026-10-10.zip"
ROOT = Path("Scheduling_Component_Handoff")

FILES = [
    "Common_Report_Component_Handoff_Pack.md",
    "IT22117014_Submission_Checklist.md",
    "IT22117014_Individual_Component_Dissertation_Submission_Review.docx",
    "IT22117014_Individual_Component_Dissertation_Submission_Review.pdf",
    "Scheduling_Remediation_Test_Evidence_2026-10-10.md",
    "Scheduling_Fresh_Integration_Test_Evidence_2026-10-10.md",
    "External_Evidence_Audit_2026-10-10.md",
    "test_scheduling_remediation.py",
    "main.py",
    "progress_tracking.py",
    "postgres_db.py",
    "academic_scheduler_service.py",
    "auth.py",
    "integration_security.py",
    "frontend/index.html",
    "frontend/script.js",
    "student_submission_portal/app.py",
    "train_workload_model.py",
    "train_workload_model_v2.py",
    "evaluate_workload_balancing.py",
    "models/workload_proxy_v2.joblib",
    "models/xgboost_duration.joblib",
    "models/workload_rf.joblib",
    "models/logistic_delay.joblib",
    "test_data_pack/README.md",
    "test_data_pack/VALIDATION_REPORT.md",
    "ieee_paper/SOURCE_AUDIT.md",
    "ieee_paper/workload_baseline_results.csv",
    "ieee_paper/workload_baseline_summary.json",
    "ieee_paper/workload_baseline_trials.csv",
    "ieee_paper/workload_proxy_v2_results.json",
    "handoff_evidence/2026-10-10/README.md",
    "handoff_evidence/2026-10-10/api_trace_summary.json",
    "handoff_evidence/2026-10-10/capture_history_fix.py",
]
FILES.extend(
    str(path.relative_to(COMPONENT)).replace("\\", "/")
    for path in sorted((COMPONENT / "handoff_evidence" / "2026-10-10").glob("*.png"))
)

missing = [relative for relative in FILES if not (COMPONENT / relative).is_file()]
if missing:
    raise SystemExit(f"Missing required handoff files: {missing}")
if len(FILES) != len(set(FILES)):
    raise SystemExit("Handoff allowlist has duplicate paths")

manifest = []
with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
    readme = (COMPONENT / "handoff_evidence" / "COMPLETE_HANDOFF_README.md").read_bytes()
    readme_name = (ROOT / "README.md").as_posix()
    archive.writestr(readme_name, readme)
    manifest.append(f"{hashlib.sha256(readme).hexdigest()}  {readme_name}")
    for relative in sorted(FILES):
        source = COMPONENT / relative
        arcname = (ROOT / relative).as_posix()
        content = source.read_bytes()
        archive.writestr(arcname, content)
        manifest.append(f"{hashlib.sha256(content).hexdigest()}  {arcname}")
    archive.writestr((ROOT / "MANIFEST.sha256").as_posix(), "\n".join(manifest) + "\n")

with ZipFile(OUTPUT) as archive:
    bad_file = archive.testzip()
    if bad_file:
        raise SystemExit(f"ZIP CRC validation failed at {bad_file}")

print(f"Created {OUTPUT}")
print(f"Bundled {len(FILES) + 1} curated files plus SHA-256 manifest")
print(f"Size: {OUTPUT.stat().st_size} bytes")
print(f"SHA-256: {hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}")
