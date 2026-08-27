# Repository Cleanup Audit

## 1. Executive Summary
This audit reviews the current state of the ResearchPilot repository, identifying dependencies, runtime requirements, historical artifacts, legacy code, and generated outputs. The goal is to provide a safe, evidence-based list of deletion candidates to clean up the repository without affecting the production application or research reproducibility.

**Key Findings:**
- The migration to PostgreSQL is fully complete. SQLite and related migration scripts/backups are no longer required for runtime but are currently tracked in Git.
- There is a large number of orphaned scratch/debugging scripts (`scratch.py`, `backend/scratch_*.py`).
- There is duplicate training infrastructure. `training/scripts/` is the canonical pipeline; `backend/scripts/training/` contains older duplicates.
- Several standalone test scripts exist in the `backend/` root which duplicate or have been superseded by the `backend/tests/` suite.

## 2. Current Application Architecture
Based on the repository structure, the architecture flows as follows:

```text
Frontend (React/Vite)
   ↓
Backend API (FastAPI - src/api/main.py)
   ↓
Services / Reviewer (src/api/services, src/reviewer)
   ↓
ML / RAG (src/core/model_singleton.py, src/core/feedback_retrieval.py)
   ↓
Database Layer (src/api/database.py, src/db/repositories.py)
   ↓
PostgreSQL (Managed via Alembic in backend/alembic/)
```

**Key Entry Points:**
- **Frontend:** `frontend/src/main.jsx` (built via Vite)
- **Backend API:** `backend/src/api/main.py` (run via Uvicorn)
- **Database Migrations:** `backend/alembic/`
- **ML Training:** `training/scripts/`

## 3. Runtime Dependency Overview
- **Python Code:** Located in `backend/src/`. Uses `requirements.txt` / `pyproject.toml`.
- **Frontend Code:** Located in `frontend/src/`. Uses `package.json`.
- **ML Models:** The backend loads `semantic_grading_model.pkl` and `weakness_svm_model.pkl`.
- **Database:** PostgreSQL is strictly required. SQLite is bypassed completely.

## 4. Backend Audit
The `backend/` directory contains active source code (`src/`), a maintained test suite (`tests/`), database migrations (`alembic/`), and active documentation (`docs/`).
However, it also contains significant clutter:
- **Scratch files:** `scratch.py`, `scratch_completeness.py`, `scratch_extract*.py`.
- **Migration scripts:** `scripts/migrate_to_postgres.py`, `scripts/post_migration_*.py`.
- **Duplicate test files:** `test_*.py` located directly in `backend/` instead of `backend/tests/`.

## 5. Frontend Audit
The frontend is relatively clean. 
- **Generated directories:** `node_modules/` and `dist/` are generated artifacts. `.gitignore` successfully ignores them.
- **Tracked files:** Only source files, `package.json`, `package-lock.json`, and `.env.example` are tracked.

## 6. Database & Migration Audit
The application recently migrated from a JSON/SQLite hybrid to PostgreSQL.
- **Active Runtime:** PostgreSQL.
- **Leftovers:**
  - `backend/data/researchpilot_dev.sqlite` (Untracked, ignored by `*.sqlite` in `.gitignore`).
  - `backend/data/migration_backups/` (Tracked).
  - JSON Reports: `backend/data/migration_report.json`, etc. (Tracked).
  - Legacy JSONs: `backend/data/analysis_history.json`, `grading_history.json`, `knowledge_graph_history.json`.

*Evidence:* `grep` reveals that SQLite is only referenced in the migration scripts. Legacy JSON history paths are defined in `core_logic.py` but never accessed for runtime operations (they are only used as test fixtures in `tests/test_supervisor_version_analysis.py`).

## 7. ML / Training Audit
- **Canonical Pipeline:** `training/` (as documented in `training/README.md`). Includes data, scripts (`01_preprocess.py` to `13_promote_models.py`), and model output directories.
- **Legacy Pipeline:** `backend/scripts/training/`, `backend/scripts/data_processing/`, `backend/scripts/evaluation/`. Documentation (`RESEARCHPILOT_TECHNICAL_GUIDE.md`) explicitly marks these as "Older or alternative".

## 8. Experiments Audit
- **Infrastructure:** `experiments/` contains reproducibility scripts (`run_controlled_reviewer_experiment.py`, `evaluate_experiment.py`).
- **Results:** `experiments/results/` contains extensive JSON and Markdown evaluation results.
*Recommendation:* Keep this directory intact for research reproducibility.

## 9. Tests Audit
- **Maintained Suite:** `backend/tests/` uses `pytest` and maintains fixtures (e.g., `postgres_fixtures.py`).
- **Orphaned Scripts:** 15+ files named `test_*.py` in the `backend/` root (e.g., `test_diag2.py`, `test_new_algo.py`). Git history and code search show they are never imported and duplicate existing coverage in `backend/tests/`.

## 10. Documentation Audit
- **Canonical Docs:** `backend/docs/` contains active architecture, deployment, and API documentation.
- **Training Docs:** `training/README.md` accurately describes the ML pipeline.
*Recommendation:* Keep all existing documentation.

## 11. Generated Artifacts
- **Python:** `__pycache__/`, `.pytest_cache/`, `venv/`.
- **Node:** `node_modules/`, `dist/`.
- **Logs:** `backend.log`, `dump.log`.

## 12. Duplicate / Legacy Code
- `backend/scripts/refactor_*.py` and `backend/scripts/create_routers.py` are one-time structural refactoring scripts.
- `backend/scripts/training/` duplicates `training/scripts/`.

---

## 13. High-Confidence Delete Candidates

### `scratch.py` and `backend/scratch*.py`
- Classification: DELETE CANDIDATE — High Confidence
- Purpose: Temporary debugging scripts used during development.
- Evidence: Not imported anywhere. Not referenced by startup scripts, documentation, or tests.
- Risk if deleted: None.

### `backend/test_*.py` (Files in backend root, not in `tests/`)
- Classification: DELETE CANDIDATE — High Confidence
- Purpose: Orphaned manual testing / reproduction scripts (e.g., `test_diag2.py`, `test_new_algo.py`).
- Evidence: Not imported anywhere. Functionality is already covered by the active pytest suite in `backend/tests/`.
- Risk if deleted: None.

### `backend/test_*.json` (e.g., `test_analyze.json`, `test_req.json`)
- Classification: DELETE CANDIDATE — High Confidence
- Purpose: Static JSON payloads for manual API testing.
- Evidence: Grep search confirms they are not loaded by any active test scripts.
- Risk if deleted: None.

### `backend/backend.log`, `backend/dump.log`
- Classification: GENERATED — Safe to Regenerate
- Purpose: Local runtime logs.
- Evidence: These are generated dynamically.
- Risk if deleted: None.

### `backend/data/migration_backups/` and `backend/data/migration_*report*.json`
- Classification: DELETE CANDIDATE — High Confidence
- Purpose: Obsolete output from the PostgreSQL migration.
- Evidence: Migration is complete. The application strictly runs on PostgreSQL.
- Risk if deleted: None.

### `backend/scripts/refactor_*.py` and `backend/scripts/create_routers.py`
- Classification: DELETE CANDIDATE — High Confidence
- Purpose: One-time scripts used to reorganize the repository architecture.
- Evidence: Refactoring is already finished and committed.
- Risk if deleted: None.

---

## 14. Medium-Confidence Delete Candidates

### `backend/scripts/training/`, `backend/scripts/data_processing/`, `backend/scripts/evaluation/`
- Classification: DELETE CANDIDATE — Medium Confidence
- Purpose: Older ML pipeline scripts.
- Evidence: `training/README.md` and `docs/RESEARCHPILOT_TECHNICAL_GUIDE.md` mark `training/scripts/` as the canonical pipeline and the backend scripts as "older". 
- Need to confirm: Ensure no unique data processing logic exists here that hasn't been ported to `training/scripts/`.

### `backend/scripts/migrate_to_postgres.py` and `post_migration_*.py`
- Classification: DELETE CANDIDATE — Medium Confidence
- Purpose: Migration execution scripts.
- Evidence: Migration is fully complete.
- Need to confirm: If you want to keep them for historical reference, move them to an `archive/` folder. Otherwise, safe to delete.

### `backend/data/*_history.json`
- Classification: DELETE CANDIDATE — Medium Confidence
- Purpose: Legacy SQLite/JSON persistence data.
- Evidence: Replaced by PostgreSQL. 
- Need to confirm: These files are currently loaded as fixtures in `backend/tests/test_supervisor_version_analysis.py` and a few others. If deleted, those specific tests will need their fixtures updated to mock data or Postgres fixtures.

---

## 15. Archive Candidates
No immediate archive recommendations. Obsolete scripts should generally be deleted since Git retains historical copies.

---

## 16. Files That Must Not Be Deleted

- **Production Source:** `backend/src/**`, `frontend/src/**`
- **Configuration:** `backend/pyproject.toml`, `backend/requirements.txt`, `backend/alembic.ini`, `frontend/package.json`, `frontend/vite.config.js`
- **Database Migrations:** `backend/alembic/**`
- **Active ML Pipeline:** `training/**`
- **Experiment Data:** `experiments/**` (Crucial for research reproducibility)
- **Startup Scripts:** `start_backend.sh`, `start_backend.ps1`
- **Documentation:** `docs/**`, `backend/docs/**`

---

## 17. Cleanup Risk Matrix

| Path | Category | Referenced By | Runtime Needed | Rebuildable | Confidence | Recommendation |
| ---- | -------- | ------------- | -------------- | ----------- | ---------- | -------------- |
| `scratch*.py` | Scratch | None | NO | YES | HIGH | Delete |
| `backend/test_*.py` (root) | Duplicate | None | NO | YES | HIGH | Delete |
| `backend/test_*.json` | Payload | None | NO | YES | HIGH | Delete |
| `backend/scripts/refactor_*.py` | One-time | None | NO | NO | HIGH | Delete |
| `backend/data/migration_backups/`| Backup | None | NO | NO | HIGH | Delete |
| `backend/scripts/training/` | Legacy | Docs only | NO | NO | MEDIUM | Delete |
| `backend/scripts/migrate_*.py` | Migration | None | NO | NO | MEDIUM | Delete |
| `backend/data/*_history.json` | Fixtures | Tests | NO | NO | MEDIUM | Update tests, then delete |

---

## 18. Recommended `.gitignore` Improvements

The current `.gitignore` is comprehensive but could explicitly ignore scratch scripts if you frequently create them.
Suggested additions to `.gitignore`:
```gitignore
# Scratch files
scratch*.py
backend/scratch*.py

# Manual test payloads
test_*.json
```
*(Note: `.env`, `venv/`, `__pycache__`, `node_modules/`, and `dist/` are already properly ignored).*

---

## 19. Proposed Clean Repository Structure

```text
.
├── backend/
│   ├── alembic/
│   ├── docs/
│   ├── src/
│   ├── scripts/      # Only active runtime/admin scripts (e.g. audit_leakage.py)
│   ├── tests/        # Consolidated pytest suite
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── pytest.ini
│
├── frontend/
│   ├── src/
│   ├── tests/
│   ├── package.json
│   └── vite.config.js
│
├── training/         # Canonical ML pipeline
│   ├── data/
│   ├── models/
│   └── scripts/
│
├── experiments/      # Reproducibility infrastructure
├── docs/
├── start_backend.sh
├── start_backend.ps1
└── README.md
```

---

## 20. Recommended Cleanup Order

### Phase 1 — Scratch & Orphaned Code (Zero Risk)
Delete `scratch.py`, `backend/scratch*.py`, `backend/test_*.py` (in root), and `backend/test_*.json`.

### Phase 2 — One-Time Scripts (Zero Risk)
Delete `backend/scripts/refactor_*.py`, `backend/scripts/create_routers.py`.

### Phase 3 — Migration Artifacts (Zero Risk)
Delete `backend/data/migration_backups/` and `backend/data/*report*.json`.

### Phase 4 — Legacy ML Pipeline (Medium Risk)
Manually verify `backend/scripts/training/`, `backend/scripts/data_processing/`, and `backend/scripts/evaluation/` against `training/scripts/`, then delete.

### Phase 5 — Legacy Data Fixtures (Medium Risk)
Update the 4 failing tests in `backend/tests/` to stop loading `backend/data/analysis_history.json`, then delete the JSON files.

---

## 21. Validation Commands Before Deletion

**Frontend Validation:**
```bash
cd frontend
npm run build
npm run test
```

**Backend Validation:**
```bash
cd backend
venv\Scripts\python.exe -m pytest -v backend/tests/
```

**Git Verification:**
```bash
git status
git diff
```

---

## 22. Final Recommendation
The repository contains a significant amount of safe-to-delete technical debt left over from rapid prototyping and the PostgreSQL migration. You can safely proceed with Phase 1, Phase 2, and Phase 3 immediately without risking runtime stability.
