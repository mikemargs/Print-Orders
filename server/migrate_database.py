from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BASELINE_TABLES = {
    "companies",
    "locations",
    "employees",
    "customers",
    "work_orders",
    "sync_events",
    "processed_operations",
}


def _looks_like_original_baseline(inspector) -> bool:
    """Return True only for the known pre-Alembic production schema.

    An absent alembic_version table is not enough evidence to stamp a database.
    This deliberately checks for post-baseline markers so an accidentally
    unversioned upgraded database is stopped before Alembic changes anything.
    """
    tables = set(inspector.get_table_names())
    if not BASELINE_TABLES.issubset(tables):
        return False
    if "artwork_files" in tables:
        return False

    employee_columns = {column["name"] for column in inspector.get_columns("employees")}
    operation_columns = {
        column["name"] for column in inspector.get_columns("processed_operations")
    }
    if "auth_version" in employee_columns:
        return False
    return "id" in operation_columns and not {"row_id", "operation_id"} & operation_columns


def migrate() -> None:
    server_dir = Path(__file__).resolve().parent
    config = Config(str(server_dir / "alembic.ini"))
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./data/multistore_server.db")
    config.set_main_option("sqlalchemy.url", database_url)
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        has_version = "alembic_version" in tables
        has_application_schema = bool(tables & BASELINE_TABLES)
        if not has_version and has_application_schema:
            if not _looks_like_original_baseline(inspector):
                raise RuntimeError(
                    "Database has application tables but no alembic_version and does not match "
                    "the known pre-Alembic baseline; cannot safely infer a migration revision. "
                    "Restore the version table or inspect/stamp the database manually."
                )
            command.stamp(config, "0001_baseline")
    finally:
        engine.dispose()
    command.upgrade(config, "head")


if __name__ == "__main__":
    migrate()
