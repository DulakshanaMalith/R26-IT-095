# Database and Persistence Documentation

## Summary

ResearchPilot runtime persistence is PostgreSQL-backed. SQLAlchemy defines the model metadata, and Alembic is the schema authority. Production schema creation must be done with:

```bash
cd backend
alembic upgrade head
```

The app no longer creates runtime tables with `Base.metadata.create_all()` and no longer writes analysis, grading, or knowledge graph history to JSON files during normal runtime.

## Runtime Tables

| Area | Tables |
| --- | --- |
| Accounts | `users`, `supervisor_profiles` |
| Student assignment | `students`, `supervisor_student_assignments` |
| Proposal workflow | `proposals`, `proposal_versions`, `analyses` |
| Review workflow | `ai_supervisor_review_drafts`, `supervisor_review_drafts`, `supervisor_reviews` |
| Delivery | `notification_logs` |
| Histories | `analysis_history_records`, `grading_records`, `knowledge_graph_records` |

History tables keep relational columns for commonly queried fields and JSONB payload columns that preserve the original response/evidence objects.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required PostgreSQL SQLAlchemy URL for application runtime. |
| `TEST_DATABASE_URL` | Required separate PostgreSQL URL for destructive tests. |
| `DATA_DIR` | Source JSON/SQLite location used by migration and archival workflows only. |

Example:

```env
DATABASE_URL=postgresql+psycopg://researchpilot:researchpilot@localhost:5432/researchpilot
TEST_DATABASE_URL=postgresql+psycopg://researchpilot:researchpilot@localhost:5432/researchpilot_test
```

## Migration

Validate source relationships before migrating:

```bash
cd backend
python scripts/migrate_to_postgres.py --validate-only --output data/migration_validation_report.json
```

Create the PostgreSQL schema:

```bash
cd backend
alembic upgrade head
```

Run the migration:

```bash
cd backend
python scripts/migrate_to_postgres.py --migrate --output data/migration_report.json
```

The migration script backs up the source SQLite database, the three JSON history files, and any history corruption backups before writing to PostgreSQL. Source files are not deleted.

## Relationship Policy

Only exact existing `analyses.analysis_id` matches are treated as workflow relationships. Historical JSON records that cannot be safely linked are preserved as standalone history rows with nullable `analysis_id`; no relationships are invented.
