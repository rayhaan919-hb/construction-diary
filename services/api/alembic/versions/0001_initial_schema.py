"""Initial canonical schema v1.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-14 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _load_initial_schema_sql() -> str:
    schema_path = (
        Path(__file__).resolve().parents[2] / "app" / "db" / "initial_schema.sql"
    )
    return schema_path.read_text(encoding="utf-8")


def upgrade() -> None:
    sql = _load_initial_schema_sql()
    bind = op.get_bind()
    dbapi_conn = bind.connection.dbapi_connection
    if dbapi_conn is None:
        raise RuntimeError("Missing DBAPI connection for initial schema migration")
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS permits_with_status")
    op.execute("DROP TABLE IF EXISTS site_log_photos CASCADE")
    op.execute("DROP TABLE IF EXISTS site_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS permit_alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS permits CASCADE")
    op.execute("DROP TABLE IF EXISTS project_members CASCADE")
    op.execute("DROP TABLE IF EXISTS projects CASCADE")
    op.execute("DROP TABLE IF EXISTS device_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP FUNCTION IF EXISTS bump_sync_version()")
    op.execute("DROP SEQUENCE IF EXISTS sync_version_seq")
