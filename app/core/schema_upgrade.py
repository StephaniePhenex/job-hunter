"""Lightweight column adds for existing DBs when not using Alembic."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def upgrade_job_table(engine: Engine) -> None:
    """Ensure `jobs` has `tags` and `applied_at` (idempotent)."""
    insp = inspect(engine)
    if not insp.has_table("jobs"):
        return

    cols = {c["name"] for c in insp.get_columns("jobs")}
    dialect = engine.dialect.name

    with engine.begin() as conn:
        if "tags" not in cols:
            if dialect == "postgresql":
                conn.execute(text("ALTER TABLE jobs ADD COLUMN tags JSONB"))
            else:
                # SQLite (and generic fallback): JSON stored as TEXT
                conn.execute(text("ALTER TABLE jobs ADD COLUMN tags TEXT"))

        if "applied_at" not in cols:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        "ALTER TABLE jobs ADD COLUMN applied_at TIMESTAMP WITH TIME ZONE"
                    )
                )
            else:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN applied_at DATETIME"))
