-- =============================================================================
-- Canonical schema (FROZEN CONTRACT v1). ai-backend-agent turns this file into
-- Alembic migration 0001 verbatim. Any change requires coordinator approval and
-- a new migration — never edit 0001 after it lands.
-- Target: PostgreSQL 16. gen_random_uuid() is built in (PG13+).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Sync infrastructure
-- -----------------------------------------------------------------------------
-- One global, monotonically increasing version shared by every synced table.
-- Used as the pull cursor (never use device clocks / updated_at as a cursor).
CREATE SEQUENCE sync_version_seq AS BIGINT START 1;

-- Every write to a synced table:
--   1. takes a transaction-scoped advisory lock (serialises version assignment
--      so a lower version can never commit AFTER a higher one has been pulled),
--   2. assigns a fresh server_version,
--   3. bumps updated_at.
CREATE OR REPLACE FUNCTION bump_sync_version() RETURNS trigger AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(724242);
  NEW.server_version := nextval('sync_version_seq');
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- Identity
-- -----------------------------------------------------------------------------
CREATE TABLE users (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email            TEXT NOT NULL,
  password_hash    TEXT NOT NULL,                       -- argon2id
  full_name        TEXT NOT NULL,
  role             TEXT NOT NULL CHECK (role IN ('OWNER', 'SUPERVISOR')),
  preferred_locale TEXT NOT NULL DEFAULT 'en' CHECK (preferred_locale IN ('en', 'ur', 'ar')),
  must_change_password BOOLEAN NOT NULL DEFAULT FALSE,  -- true for invited users with temp password
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX users_email_lower_uq ON users (LOWER(email));

CREATE TABLE refresh_tokens (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash    TEXT NOT NULL UNIQUE,                   -- sha256 of opaque token; raw token never stored
  device_label  TEXT,
  expires_at    TIMESTAMPTZ NOT NULL,                   -- 60-day sliding window, rotated on every refresh
  revoked_at    TIMESTAMPTZ,
  replaced_by   UUID REFERENCES refresh_tokens(id),     -- rotation chain; reuse of a rotated token revokes the chain
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_used_at  TIMESTAMPTZ
);
CREATE INDEX refresh_tokens_user_idx ON refresh_tokens (user_id);

CREATE TABLE device_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  fcm_token   TEXT NOT NULL UNIQUE,
  platform    TEXT NOT NULL DEFAULT 'ANDROID' CHECK (platform IN ('ANDROID')),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Projects & membership (synced DOWN to mobile; created/edited on web only)
-- -----------------------------------------------------------------------------
CREATE TABLE projects (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT NOT NULL,
  site_address     TEXT NOT NULL,
  owner_phone      TEXT,
  timezone         TEXT NOT NULL DEFAULT 'Asia/Karachi',  -- IANA tz; defines "today" and log_date
  allow_photo_gps  BOOLEAN NOT NULL DEFAULT FALSE,        -- if false, mobile strips EXIF GPS
  created_by       UUID NOT NULL REFERENCES users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at       TIMESTAMPTZ,
  server_version   BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX projects_server_version_idx ON projects (server_version);
CREATE TRIGGER projects_sync_version BEFORE INSERT OR UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION bump_sync_version();

CREATE TABLE project_members (
  project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('OWNER', 'SUPERVISOR')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ,                           -- removal is a tombstone so mobile learns about it
  server_version  BIGINT NOT NULL DEFAULT 0,
  PRIMARY KEY (project_id, user_id)
);
CREATE INDEX project_members_user_idx ON project_members (user_id);
CREATE INDEX project_members_server_version_idx ON project_members (server_version);
CREATE TRIGGER project_members_sync_version BEFORE INSERT OR UPDATE ON project_members
  FOR EACH ROW EXECUTE FUNCTION bump_sync_version();

-- -----------------------------------------------------------------------------
-- Permits (synced BOTH ways; status is DERIVED, never stored)
-- -----------------------------------------------------------------------------
CREATE TABLE permits (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),  -- clients may supply their own UUID
  project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  permit_name         TEXT NOT NULL,
  authority           TEXT NOT NULL,
  permit_number       TEXT,
  issue_date          DATE,
  expiry_date         DATE NOT NULL,
  document_photo_uri  TEXT,                              -- storage URI (gs://... or local://...)
  created_by          UUID NOT NULL REFERENCES users(id),
  client_updated_at   TIMESTAMPTZ,                       -- device clock; audit only, never used for ordering
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at          TIMESTAMPTZ,
  server_version      BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX permits_project_idx ON permits (project_id) WHERE deleted_at IS NULL;
CREATE INDEX permits_expiry_idx ON permits (expiry_date) WHERE deleted_at IS NULL;
CREATE INDEX permits_server_version_idx ON permits (server_version);
CREATE TRIGGER permits_sync_version BEFORE INSERT OR UPDATE ON permits
  FOR EACH ROW EXECUTE FUNCTION bump_sync_version();

-- Status relative to the PROJECT's local date. EXPIRING_SOON window = 14 days
-- (keep in sync with PERMIT_EXPIRING_SOON_DAYS default; the view is the source of truth).
CREATE VIEW permits_with_status AS
SELECT
  p.*,
  (p.expiry_date - (NOW() AT TIME ZONE pr.timezone)::date) AS days_to_expiry,
  CASE
    WHEN p.expiry_date <  (NOW() AT TIME ZONE pr.timezone)::date      THEN 'EXPIRED'
    WHEN p.expiry_date <= (NOW() AT TIME ZONE pr.timezone)::date + 14 THEN 'EXPIRING_SOON'
    ELSE 'ACTIVE'
  END AS status
FROM permits p
JOIN projects pr ON pr.id = p.project_id;

CREATE TABLE permit_alerts (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  permit_id          UUID NOT NULL REFERENCES permits(id) ON DELETE CASCADE,
  threshold          TEXT NOT NULL CHECK (threshold IN ('D30', 'D14', 'D7', 'D1', 'EXPIRED')),
  channel            TEXT NOT NULL CHECK (channel IN ('CONSOLE', 'EMAIL', 'FCM')),
  recipient_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  sent_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (permit_id, threshold, channel, recipient_user_id)   -- dedupe: each alert fires once
);

-- -----------------------------------------------------------------------------
-- Site logs: one row per voice recording (synced BOTH ways)
-- -----------------------------------------------------------------------------
CREATE TABLE site_logs (
  id                   UUID PRIMARY KEY,                 -- ALWAYS client-generated (offline-first)
  project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  author_id            UUID NOT NULL REFERENCES users(id),
  log_date             DATE NOT NULL,                    -- project-local date, computed on device
  recorded_at          TIMESTAMPTZ NOT NULL,             -- device clock (audit/display only)
  notes                TEXT,                             -- optional typed note

  -- audio (client-owned except audio_upload_status)
  audio_uri            TEXT,                             -- storage URI; was audio_url in draft schema
  audio_duration_ms    INTEGER CHECK (audio_duration_ms IS NULL OR audio_duration_ms BETWEEN 0 AND 300000),
  audio_upload_status  TEXT NOT NULL DEFAULT 'NONE'
                         CHECK (audio_upload_status IN ('NONE', 'PENDING', 'UPLOADED')),

  -- AI extraction (server-owned)
  extraction_status    TEXT NOT NULL DEFAULT 'NOT_STARTED'
                         CHECK (extraction_status IN ('NOT_STARTED', 'PENDING', 'PROCESSING', 'DONE', 'FAILED')),
  extraction_attempts  INTEGER NOT NULL DEFAULT 0,
  extraction_error     TEXT,
  extraction_model     TEXT,
  extracted_at         TIMESTAMPTZ,
  transcript           TEXT,                             -- original spoken language
  detected_language    TEXT CHECK (detected_language IS NULL OR detected_language IN ('ur', 'en', 'ar', 'mixed', 'unknown')),

  -- structured_summary shape (English-normalised):
  --   { "tasks_completed": [str], "labor_count": int|null,
  --     "material_deliveries": [str], "blockers": [str] }
  -- Written by the server after extraction, or by the client when edited_by_human = true.
  structured_summary   JSONB,
  edited_by_human      BOOLEAN NOT NULL DEFAULT FALSE,

  client_updated_at    TIMESTAMPTZ NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at           TIMESTAMPTZ,
  server_version       BIGINT NOT NULL DEFAULT 0
  -- NOTE: draft column sync_status was removed — sync state is a client-side (Room) concern.
);
CREATE INDEX site_logs_project_date_idx ON site_logs (project_id, log_date DESC) WHERE deleted_at IS NULL;
CREATE INDEX site_logs_extraction_idx ON site_logs (extraction_status) WHERE extraction_status IN ('PENDING', 'PROCESSING');
CREATE INDEX site_logs_server_version_idx ON site_logs (server_version);
CREATE TRIGGER site_logs_sync_version BEFORE INSERT OR UPDATE ON site_logs
  FOR EACH ROW EXECUTE FUNCTION bump_sync_version();

-- Photos attached to a log; one row per photo so each upload is tracked independently.
CREATE TABLE site_log_photos (
  id               UUID PRIMARY KEY,                     -- client-generated
  site_log_id      UUID NOT NULL REFERENCES site_logs(id) ON DELETE CASCADE,
  storage_uri      TEXT NOT NULL,
  upload_status    TEXT NOT NULL DEFAULT 'PENDING' CHECK (upload_status IN ('PENDING', 'UPLOADED')),
  width            INTEGER,
  height           INTEGER,
  byte_size        INTEGER,
  taken_at         TIMESTAMPTZ,
  sort_order       INTEGER NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at       TIMESTAMPTZ,
  server_version   BIGINT NOT NULL DEFAULT 0
);
CREATE INDEX site_log_photos_log_idx ON site_log_photos (site_log_id) WHERE deleted_at IS NULL;
CREATE INDEX site_log_photos_server_version_idx ON site_log_photos (server_version);
CREATE TRIGGER site_log_photos_sync_version BEFORE INSERT OR UPDATE ON site_log_photos
  FOR EACH ROW EXECUTE FUNCTION bump_sync_version();
