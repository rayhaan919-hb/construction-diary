"""Media upload reservations and auditable orphan cleanup history.

Revision ID: 0003_media_reservations
Revises: 0002_commercial_saas_hardening
Create Date: 2026-11-15 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_media_reservations"
down_revision: str | Sequence[str] | None = "0002_commercial_saas_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE media_reservations (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
            project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind            TEXT NOT NULL CHECK (kind IN ('AUDIO', 'PHOTO', 'PERMIT_DOC')),
            object_id       UUID NOT NULL,
            status          TEXT NOT NULL DEFAULT 'ACTIVE'
                                CHECK (status IN ('ACTIVE', 'CONSUMED', 'EXPIRED', 'CANCELLED')),
            expires_at      TIMESTAMPTZ NOT NULL,
            consumed_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_media_reservations_active_target "
        "ON media_reservations (kind, object_id) WHERE status = 'ACTIVE'"
    )
    op.execute(
        "CREATE INDEX idx_media_reservations_expires "
        "ON media_reservations (status, expires_at)"
    )
    op.execute(
        "CREATE INDEX idx_media_reservations_user "
        "ON media_reservations (user_id, project_id)"
    )

    op.execute(
        """
        ALTER TABLE upload_tickets
            ADD COLUMN reservation_id UUID REFERENCES media_reservations(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX idx_upload_tickets_expires "
        "ON upload_tickets (status, expires_at)"
    )

    op.execute(
        """
        CREATE TABLE media_cleanup_runs (
            id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            started_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at                 TIMESTAMPTZ,
            status                       TEXT NOT NULL DEFAULT 'RUNNING'
                                             CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
            dry_run                      BOOLEAN NOT NULL DEFAULT FALSE,
            expired_tickets_cleaned      INTEGER NOT NULL DEFAULT 0,
            expired_reservations_cleaned INTEGER NOT NULL DEFAULT 0,
            incomplete_uploads_cleaned   INTEGER NOT NULL DEFAULT 0,
            unattached_objects_deleted   INTEGER NOT NULL DEFAULT 0,
            failed_jobs_pruned           INTEGER NOT NULL DEFAULT 0,
            bytes_reclaimed              BIGINT NOT NULL DEFAULT 0,
            details                      JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_summary                TEXT
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_media_cleanup_runs_started "
        "ON media_cleanup_runs (started_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_media_cleanup_runs_started")
    op.execute("DROP TABLE IF EXISTS media_cleanup_runs")
    op.execute("DROP INDEX IF EXISTS idx_upload_tickets_expires")
    op.execute("ALTER TABLE upload_tickets DROP COLUMN IF EXISTS reservation_id")
    op.execute("DROP INDEX IF EXISTS idx_media_reservations_user")
    op.execute("DROP INDEX IF EXISTS idx_media_reservations_expires")
    op.execute("DROP INDEX IF EXISTS uq_media_reservations_active_target")
    op.execute("DROP TABLE IF EXISTS media_reservations")
