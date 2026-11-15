# Release Notes — Construction Diary v1.0.0 (Commercial Hardening Release)

**Release Date:** 2026-11-15  
**Target Branch / Tag Readiness:** `main` (v1.0.0 Candidate)

---

## Highlights in v1.0.0

### Security, Media Reservations & Web Hardening
- Migrated authentication to Argon2id hashing with transparent rehash upgrades, timing-safe dummy checks, progressive account lockout, per-IP rate limiting, password reset email/token flows, and refresh-token rotation + family reuse revocation.
- Implemented offline-compatible media upload reservations (`POST /v1/media/reservations`, Alembic `0003_media_reservations.py`) binding client-generated UUIDs to the authenticated user, project, and organization, alongside single-use `UploadTicket` verification, immutable object keys, magic-byte + MIME + size validation (`25 MB`), replay/overwrite protection, and auditable orphan media cleanup (`media_cleanup_runs`, `app.jobs.media_cleanup`).
- Fixed `PATCH /v1/logs/{log_id}` human-edit tracking so editing field notes consistently sets `edited_by_human = true` across API responses, web timeline badges, and PDF exports (while honoring explicit overrides).
- Upgraded `apps/web` to `next@^16.4.6` (`eslint-config-next@^16.4.6`) and migrated middleware to `src/proxy.ts`, eliminating high/critical production npm advisories (`npm audit --omit=dev --audit-level=high` clean).
- Extracted dynamic request-scoped CSP generation (`apps/web/src/lib/csp.ts`, applied in `src/proxy.ts` + `next.config.ts`) to keep `https:`-only media directives in production while permitting explicit local loopback API origins (`127.0.0.1` / `localhost`) in local/E2E verification.
- Built Web BFF CSRF origin verification, SSRF IP/DNS blocking for PDF photo downloads (`photo-fetcher.ts`), Organization Admin Console (`/organization`), team onboarding (`/register`, `/invite`, `/forgot-password`, `/reset-password`), and offline demo mode (`NEXT_PUBLIC_DEMO_MODE=true`).

### Offline-First Android (`targetSdk = 36`) & Release Signing
- Upgraded Android `targetSdk` to `36` (`compileSdk = 37`, `minSdk = 26`) with static compatibility verification across Android 13–16 behaviors ([docs/14-android-device-testing-checklist.md](docs/14-android-device-testing-checklist.md)).
- Removed placeholder `.example.com` production URLs and implemented strict fail-closed environment separation (`debug`/`dev`, `staging`, `release`/`prod`) plus fail-closed release signing (`GradleException` on missing HTTPS endpoint or keystore secrets) and automated `build-metadata.json` emission ([docs/15-android-release-signing.md](docs/15-android-release-signing.md)).
- Updated Android `MediaUploader.kt` to reserve target UUIDs via `/v1/media/reservations` before requesting upload tickets, upgraded storage to Keystore `AES/GCM/NoPadding`, preserved `CONFLICT_PENDING` dirty edits, cleaned remote photo tombstones, added full English/Urdu (`values-ur/`)/Arabic (`values-ar/`) UI localization, and supported optional `google-services.json`.

### Infrastructure, Disaster Recovery & CI/CD
- Verified destructive PostgreSQL 16 + local media backup/restore roundtrip (`infra/scripts/verify-backup-restore.sh`) including sorted SHA-256 parity across restored media files and live FastAPI authentication against the restored database.
- Fixed CI workflow `.github/workflows/ci.yml` (`actions/setup-java@v5`, deterministic Android SDK & license configuration without deprecated Node 20 `setup-android@v3`, `npm audit --omit=dev --audit-level=high`, dev dependency reporting, shell syntax checks, fail-closed `bundleRelease` check, and signed `staging` APK/AAB artifact verification) and fixed `pgserver` library/binary/URI handling in `test_postgres_backup_and_restore_roundtrip`.
- Added live Chromium full-stack Playwright E2E coverage (`apps/web/e2e/commercial-readiness.spec.ts`) exercising signup, invitations, RBAC, projects, offline media reservations/sync, lightbox, note editing, permit CRUD, PDF export, and auth guards.

---

## Pre-Production Requirements & Known Limitations
- **External Cloud & Signing Secrets Required:** Live GCP rollout (`infra/scripts/deploy-gcp.sh`, Cloud Run, Cloud SQL, GCS, Secret Manager, Cloud Tasks, Vertex AI, Stripe, SMTP) and Play Console production `release` AAB signing (`PROD_API_BASE_URL` + `ANDROID_KEYSTORE_*`) require external credentials not stored in git.
- **Physical Device Hardware QA:** Physical/emulator interactive testing across Android 13–16 must be completed before promoting a Play Store release ([docs/14-android-device-testing-checklist.md](docs/14-android-device-testing-checklist.md)).
