from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def load_database_url() -> str:
    for line in Path("backend/.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1]
    return os.environ["DATABASE_URL"]


def main() -> None:
    engine = create_engine(load_database_url())
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema="public"))
    payload: dict[str, object] = {"tables": tables, "schema": {}}
    with engine.connect() as conn:
        payload["alembic_version"] = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    schema: dict[str, object] = {}
    for table in tables:
        columns = inspector.get_columns(table, schema="public")
        schema[table] = {
            "primary_key": inspector.get_pk_constraint(table, schema="public").get("constrained_columns", []),
            "foreign_keys": [
                {
                    "columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table"),
                    "referred_columns": fk.get("referred_columns", []),
                }
                for fk in inspector.get_foreign_keys(table, schema="public")
            ],
            "indexes": [
                {
                    "name": idx.get("name"),
                    "columns": idx.get("column_names", []),
                    "unique": bool(idx.get("unique")),
                }
                for idx in inspector.get_indexes(table, schema="public")
            ],
            "jsonb_columns": [
                col["name"]
                for col in columns
                if str(col["type"]).upper() == "JSONB"
            ],
            "nullable_relationship_columns": [
                col["name"]
                for col in columns
                if col.get("nullable")
                and (
                    col["name"].endswith("_id")
                    or col["name"] in {"request_id", "current_version_id"}
                )
            ],
        }
    payload["schema"] = schema
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
