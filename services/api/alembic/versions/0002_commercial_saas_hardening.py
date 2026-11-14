"""Commercial SaaS multi-tenancy, upload tickets, durable AI queue, and audit logs.

Revision ID: 0002_commercial_saas_hardening
Revises: 0001_initial_schema
Create Date: 2026-11-15 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_commercial_saas_hardening"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Organizations, org memberships, invitations & billing events
    op.execute(
        """
        CREATE TABLE organizations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'SUSPENDED', 'PENDING_DELETION')),
            plan_tier TEXT NOT NULL DEFAULT 'STARTER'
                CHECK (plan_tier IN ('FREE', 'STARTER', 'PRO', 'ENTERPRISE')),
            subscription_status TEXT NOT NULL DEFAULT 'TRIALING'
                CHECK (subscription_status IN ('TRIALING', 'ACTIVE', 'PAST_DUE', 'CANCELED')),
            billing_provider TEXT NOT NULL DEFAULT 'stripe',
            billing_customer_id TEXT,
            billing_subscription_id TEXT,
            trial_ends_at TIMESTAMPTZ,
            current_period_end TIMESTAMPTZ,
            max_projects INTEGER NOT NULL DEFAULT 25 CHECK (max_projects >= 1),
            max_seats INTEGER NOT NULL DEFAULT 50 CHECK (max_seats >= 1),
            max_storage_bytes BIGINT NOT NULL DEFAULT 53687091200 CHECK (max_storage_bytes >= 0),
            max_ai_extractions_monthly INTEGER NOT NULL DEFAULT 1000
                CHECK (max_ai_extractions_monthly >= 0),
            ai_extractions_this_month INTEGER NOT NULL DEFAULT 0
                CHECK (ai_extractions_this_month >= 0),
            storage_bytes_used BIGINT NOT NULL DEFAULT 0 CHECK (storage_bytes_used >= 0),
            billing_month TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC', 'YYYY-MM'),
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE organization_members (
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (
                role IN ('OWNER', 'ADMIN', 'PROJECT_MANAGER', 'SUPERVISOR', 'WORKER', 'VIEWER')
            ),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ,
            PRIMARY KEY (organization_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_org_members_user ON organization_members (user_id, deleted_at)"
    )

    op.execute(
        """
        CREATE TABLE organization_invitations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
            email TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (
                role IN ('OWNER', 'ADMIN', 'PROJECT_MANAGER', 'SUPERVISOR', 'WORKER', 'VIEWER')
            ),
            token_hash TEXT NOT NULL UNIQUE,
            invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            accepted_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_org_invites_org_email "
        "ON organization_invitations (organization_id, email)"
    )

    op.execute(
        """
        CREATE TABLE billing_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            external_event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_billing_events_org ON billing_events (organization_id, processed_at DESC)"
    )

    # 2. Password reset tokens & user/auth hardening
    op.execute(
        """
        CREATE TABLE password_reset_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_pw_reset_user ON password_reset_tokens (user_id, expires_at)"
    )

    op.execute(
        """
        DO $$
        DECLARE cname text;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'users'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%role%';
            IF cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE users DROP CONSTRAINT ' || quote_ident(cname);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE users
            ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE RESTRICT,
            ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'
                CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DELETED')),
            ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN locked_until TIMESTAMPTZ,
            ADD COLUMN last_login_at TIMESTAMPTZ,
            ADD COLUMN password_changed_at TIMESTAMPTZ,
            ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ADD CONSTRAINT users_role_check CHECK (
                role IN ('OWNER', 'ADMIN', 'PROJECT_MANAGER', 'SUPERVISOR', 'WORKER', 'VIEWER')
            )
        """
    )
    op.execute("CREATE INDEX idx_users_org ON users (organization_id)")

    # 3. Multi-tenant projects + expanded project_members roles
    op.execute(
        """
        ALTER TABLE projects
            ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE
        """
    )
    op.execute("CREATE INDEX idx_projects_org ON projects (organization_id, deleted_at)")
    op.execute("CREATE INDEX idx_projects_created_by ON projects (created_by)")

    op.execute(
        """
        DO $$
        DECLARE cname text;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'project_members'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%role%';
            IF cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE project_members DROP CONSTRAINT ' || quote_ident(cname);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE project_members
            ADD CONSTRAINT project_members_role_check CHECK (
                role IN ('OWNER', 'ADMIN', 'PROJECT_MANAGER', 'SUPERVISOR', 'WORKER', 'VIEWER')
            )
        """
    )

    # 4. Upload tickets (unique immutable keys bound to user + project + object + size + MIME)
    op.execute(
        """
        CREATE TABLE upload_tickets (
            id UUID PRIMARY KEY,
            organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('AUDIO', 'PHOTO', 'PERMIT_DOC')),
            object_id UUID NOT NULL,
            object_key TEXT NOT NULL UNIQUE,
            storage_uri TEXT NOT NULL UNIQUE,
            content_type TEXT NOT NULL,
            expected_byte_size BIGINT NOT NULL CHECK (expected_byte_size >= 1),
            actual_byte_size BIGINT,
            sha256 TEXT,
            status TEXT NOT NULL DEFAULT 'ISSUED'
                CHECK (status IN ('ISSUED', 'UPLOADED', 'COMPLETED', 'EXPIRED', 'REVOKED')),
            expires_at TIMESTAMPTZ NOT NULL,
            uploaded_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_upload_tickets_lookup ON upload_tickets (project_id, kind, object_id)"
    )
    op.execute(
        "CREATE INDEX idx_upload_tickets_user ON upload_tickets (user_id, created_at DESC)"
    )

    # 5. Durable AI extraction jobs + extended permit/photo columns
    op.execute(
        """
        CREATE TABLE extraction_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            target_type TEXT NOT NULL CHECK (
                target_type IN ('SITE_LOG', 'SITE_LOG_PHOTO', 'PERMIT')
            ),
            target_id UUID NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELED')),
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_until TIMESTAMPTZ,
            worker_id TEXT,
            last_error TEXT,
            result_payload JSONB,
            model_name TEXT,
            cloud_task_name TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_extraction_jobs_due ON extraction_jobs (status, next_run_at) "
        "WHERE status IN ('PENDING', 'PROCESSING')"
    )
    op.execute(
        "CREATE INDEX idx_extraction_jobs_target ON extraction_jobs (target_type, target_id)"
    )

    op.execute(
        """
        ALTER TABLE permits
            ADD COLUMN document_upload_status TEXT NOT NULL DEFAULT 'NONE'
                CHECK (document_upload_status IN ('NONE', 'PENDING', 'UPLOADED')),
            ADD COLUMN ai_extracted_data JSONB
        """
    )
    op.execute("CREATE INDEX idx_permits_created_by ON permits (created_by)")

    op.execute(
        """
        ALTER TABLE site_log_photos
            ALTER COLUMN byte_size TYPE BIGINT,
            ADD COLUMN ai_caption TEXT,
            ADD COLUMN ai_labels JSONB
        """
    )
    op.execute("CREATE INDEX idx_site_logs_author ON site_logs (author_id)")

    # Fix permit_alerts renewal dedupe by tracking permit_expiry_date
    op.execute(
        """
        ALTER TABLE permit_alerts
            ADD COLUMN permit_expiry_date DATE
        """
    )
    op.execute(
        """
        DO $$
        DECLARE cname text;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'permit_alerts'::regclass
              AND contype = 'u';
            IF cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE permit_alerts DROP CONSTRAINT ' || quote_ident(cname);
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_permit_alerts_dedupe_v2 "
        "ON permit_alerts (permit_id, threshold, channel, recipient_user_id, permit_expiry_date)"
    )
    op.execute(
        "CREATE INDEX idx_permit_alerts_recipient ON permit_alerts (recipient_user_id)"
    )

    # Fix refresh_tokens FK ON DELETE + missing indexes
    op.execute(
        """
        DO $$
        DECLARE cname text;
        BEGIN
            SELECT conname INTO cname
            FROM pg_constraint
            WHERE conrelid = 'refresh_tokens'::regclass
              AND contype = 'f'
              AND pg_get_constraintdef(oid) LIKE '%replaced_by%';
            IF cname IS NOT NULL THEN
                EXECUTE 'ALTER TABLE refresh_tokens DROP CONSTRAINT ' || quote_ident(cname);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE refresh_tokens
            ADD CONSTRAINT refresh_tokens_replaced_by_fkey
            FOREIGN KEY (replaced_by) REFERENCES refresh_tokens(id) ON DELETE SET NULL
        """
    )
    op.execute("CREATE INDEX idx_refresh_replaced_by ON refresh_tokens (replaced_by)")
    op.execute("CREATE INDEX idx_refresh_expires_at ON refresh_tokens (expires_at)")
    op.execute("CREATE INDEX idx_device_tokens_user ON device_tokens (user_id)")

    # 6. Immutable audit_logs table + protection trigger
    op.execute(
        """
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sequence_num BIGSERIAL NOT NULL,
            organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
            actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            actor_email TEXT,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            request_id TEXT,
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_logs_org_created ON audit_logs (organization_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_audit_logs_actor ON audit_logs (actor_user_id, created_at DESC)"
    )
    op.execute("CREATE INDEX idx_audit_logs_action ON audit_logs (action, created_at DESC)")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs are append-only and cannot be modified or deleted'
                USING ERRCODE = '42501';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation()
        """
    )

    # 7. Recreate permits_with_status view honoring configurable threshold & new columns
    op.execute("DROP VIEW IF EXISTS permits_with_status")
    op.execute(
        """
        CREATE VIEW permits_with_status AS
        SELECT
            p.id,
            p.project_id,
            p.permit_name,
            p.authority,
            p.permit_number,
            p.issue_date,
            p.expiry_date,
            p.document_photo_uri,
            p.created_by,
            p.client_updated_at,
            p.created_at,
            p.updated_at,
            p.deleted_at,
            p.server_version,
            (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) AS days_to_expiry,
            CASE
                WHEN (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) < 0 THEN 'EXPIRED'
                WHEN (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date)
                    <= COALESCE(
                        NULLIF(current_setting('app.permit_expiring_soon_days', true), '')::int,
                        14
                    )
                    THEN 'EXPIRING_SOON'
                ELSE 'ACTIVE'
            END AS status,
            p.document_upload_status,
            p.ai_extracted_data
        FROM permits p
        JOIN projects pr ON pr.id = p.project_id
        WHERE p.deleted_at IS NULL
        """
    )

    # 8. Preserve existing customer data by assigning legacy rows to a default org if any exist
    op.execute(
        """
        DO $$
        DECLARE def_org_id UUID;
        DECLARE first_owner UUID;
        BEGIN
            IF EXISTS (SELECT 1 FROM users WHERE organization_id IS NULL)
               OR EXISTS (SELECT 1 FROM projects WHERE organization_id IS NULL) THEN
                SELECT id INTO first_owner FROM users
                WHERE role = 'OWNER' ORDER BY created_at LIMIT 1;
                INSERT INTO organizations (name, slug, plan_tier, subscription_status, created_by)
                VALUES ('Default Construction Org', 'default-org', 'PRO', 'ACTIVE', first_owner)
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                RETURNING id INTO def_org_id;

                UPDATE users SET organization_id = def_org_id WHERE organization_id IS NULL;
                UPDATE projects SET organization_id = def_org_id WHERE organization_id IS NULL;

                INSERT INTO organization_members (organization_id, user_id, role)
                SELECT def_org_id, u.id, u.role FROM users u
                ON CONFLICT DO NOTHING;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS permits_with_status")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()")
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP INDEX IF EXISTS idx_device_tokens_user")
    op.execute("DROP INDEX IF EXISTS idx_refresh_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_refresh_replaced_by")
    op.execute("DROP INDEX IF EXISTS idx_permit_alerts_recipient")
    op.execute("DROP INDEX IF EXISTS idx_permit_alerts_dedupe_v2")
    op.execute("ALTER TABLE permit_alerts DROP COLUMN IF EXISTS permit_expiry_date")
    op.execute(
        "ALTER TABLE permit_alerts "
        "ADD CONSTRAINT permit_alerts_permit_id_threshold_channel_recipient_user_id_key "
        "UNIQUE (permit_id, threshold, channel, recipient_user_id)"
    )
    op.execute("DROP INDEX IF EXISTS idx_site_logs_author")
    op.execute(
        "ALTER TABLE site_log_photos "
        "DROP COLUMN IF EXISTS ai_labels, DROP COLUMN IF EXISTS ai_caption"
    )
    op.execute("DROP INDEX IF EXISTS idx_permits_created_by")
    op.execute(
        "ALTER TABLE permits "
        "DROP COLUMN IF EXISTS ai_extracted_data, "
        "DROP COLUMN IF EXISTS document_upload_status"
    )
    op.execute(
        """
        CREATE VIEW permits_with_status AS
        SELECT
            p.*,
            (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) AS days_to_expiry,
            CASE
                WHEN (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) < 0 THEN 'EXPIRED'
                WHEN (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) <= 14
                    THEN 'EXPIRING_SOON'
                ELSE 'ACTIVE'
            END AS status
        FROM permits p
        JOIN projects pr ON pr.id = p.project_id
        WHERE p.deleted_at IS NULL
        """
    )
    op.execute("DROP TABLE IF EXISTS extraction_jobs")
    op.execute("DROP TABLE IF EXISTS upload_tickets")
    op.execute("ALTER TABLE project_members DROP CONSTRAINT IF EXISTS project_members_role_check")
    op.execute("DROP INDEX IF EXISTS idx_projects_created_by")
    op.execute("DROP INDEX IF EXISTS idx_projects_org")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS organization_id")
    op.execute("DROP INDEX IF EXISTS idx_users_org")
    op.execute(
        "ALTER TABLE users "
        "DROP CONSTRAINT IF EXISTS users_role_check, "
        "DROP COLUMN IF EXISTS updated_at, "
        "DROP COLUMN IF EXISTS password_changed_at, "
        "DROP COLUMN IF EXISTS last_login_at, "
        "DROP COLUMN IF EXISTS locked_until, "
        "DROP COLUMN IF EXISTS failed_login_attempts, "
        "DROP COLUMN IF EXISTS token_version, "
        "DROP COLUMN IF EXISTS status, "
        "DROP COLUMN IF EXISTS organization_id"
    )
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")
    op.execute("DROP TABLE IF EXISTS billing_events")
    op.execute("DROP TABLE IF EXISTS organization_invitations")
    op.execute("DROP TABLE IF EXISTS organization_members")
    op.execute("DROP TABLE IF EXISTS organizations")
