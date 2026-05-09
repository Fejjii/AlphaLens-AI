"""Best-effort DDL fixes for local dev when ORM adds columns but tables already exist.

TODO: Replace with Alembic migrations for staging/prod.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from alphalens.core.logging import get_logger

log = get_logger(__name__)


def ensure_dev_report_table_schema(engine: Engine, *, app_env: str) -> None:
    """Add ``reports.memo_metadata`` if missing (dev/test only).

    ``Base.metadata.create_all`` does not ALTER existing tables, so older Postgres
    volumes fail inserts with ``UndefinedColumn`` until this runs.
    """
    if app_env not in {"dev", "test"}:
        return
    try:
        insp = inspect(engine)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("report_schema_guard_inspect_failed", error=f"{exc.__class__.__name__}: {exc}")
        return
    if not insp.has_table("reports"):
        return
    columns = {c["name"] for c in insp.get_columns("reports")}
    if "memo_metadata" in columns:
        return
    dialect = engine.dialect.name
    log.warning(
        "report_schema_guard_adding_column",
        table="reports",
        column="memo_metadata",
        dialect=dialect,
        hint="TODO: add Alembic migration; for full DB reset see docker compose down -v",
    )
    stmt: str
    if dialect == "postgresql":
        stmt = (
            "ALTER TABLE reports ADD COLUMN IF NOT EXISTS memo_metadata JSON NOT NULL "
            "DEFAULT '{}'::json"
        )
    elif dialect == "sqlite":
        stmt = "ALTER TABLE reports ADD COLUMN memo_metadata TEXT NOT NULL DEFAULT '{}'"
    else:  # pragma: no cover - rare local setups
        log.warning("report_schema_guard_unsupported_dialect", dialect=dialect)
        return
    with engine.begin() as conn:
        conn.execute(text(stmt))
