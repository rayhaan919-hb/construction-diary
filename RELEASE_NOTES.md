# Release Notes — Construction Diary v1.0.0 (Commercial Hardening Release)

**Release Date:** 2026-11-15  
**Target Branch / Tag Readiness:** `main` (v1.0.0 Candidate)

---

## Highlights in v1.0.0

### Security & Authentication
- Migrated authentication to Argon2id hashing with transparent rehash upgrades, timing-safe dummy checks, progressive account lockout, per-IP rate limiting, password reset email/token flows, and refresh-token rotation + family reuse revocation.
- Replaced deterministic user-supplied storage paths with single-use `UploadTicket` issuance bound to `(user, project, target_record)` + byte-size bounds + magic-byte signature validation + path traversal sanitization.
- Enforced fail-closed startup configuration validation (`ENV=staging|production`) requiring 32+ char distinct secrets, TLS `CORS_ORIGINS`, GCS backend, non-default database credentials, and Google Secret Manager (`sm://`) support.

### Multi-Tenant SaaS & Web Portal
- Added organization tenancy (`organizations`, `organization_members`, `organization_invitations`, `audit_logs`, `billing_events`) via Alembic migration `0002_commercial_saas_hardening.py` while keeping `initial_schema.sql` byte-identical to `contracts/schema.sql`.
- Built Web BFF CSRF origin verification, strict CSP/HSTS/XFO security headers, SSRF-hardened photo downloads for bilingual PDF exports, Organization Admin Console (`/organization`), team onboarding (`/register`, `/invite`, `/forgot-password`, `/reset-password`), and offline demo mode (`NEXT_PUBLIC_DEMO_MODE=true`).

### Offline-First Android & AI Extraction
- Upgraded Android session storage to Android Keystore `AES/GCM/NoPadding` encryption, ensured full credential + FCM cleanup on logout (`clearAllSettingsOnLogout`), enforced HTTPS for release `API_BASE_URL` builds, disabled release cleartext HTTP, and added full English, Urdu (`values-ur/`), and Arabic (`values-ar/`) UI localization.
- Fixed offline conflict preservation (`CONFLICT_PENDING` keeps `syncDirty = true`), remote photo tombstone cleanup (DB + local disk), remote voice note playback, and graceful `google-services.json`-optional FCM initialization.
- Upgraded AI extraction to durable DB queue state (`extraction_jobs`) with Cloud Tasks dispatch, stale lease recovery, Pydantic validation, and retry endpoints.

### Infrastructure, Testing & Compliance
- Added Cloud Run / Cloud SQL / GCS / Secret Manager setup, deployment, backup, and restore verification scripts (`infra/scripts/*.sh`) plus WIF CI/CD workflows (`.github/workflows/{ci,cd}.yml`).
- Verified across Backend (`pytest` 32 passed, `ruff`, `mypy`), Web (`vitest` 39 passed, `tsc`, `eslint`, `next build`), and Android (`testDebugUnitTest` 34 passed, `lintDebug`, release builds).
