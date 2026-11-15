# Final Commercial Readiness Report — Construction Diary (`site-diary`)

**Report Date:** 2026-11-15  
**Repository:** `https://github.com/rayhaan919-hb/construction-diary.git` (`main`)  
**Commercial Readiness Lineage:** `1bf6839` -> `COMMERCIAL_READINESS_AUDIT.md` (`e44ce99`) -> Backend & SaaS Hardening (`f1cfe65`..`a170e88`) -> Final Release Remediation & Verification (`a170e88..HEAD`)  
**Detailed Issue Ledger:** [FINAL_RELEASE_BLOCKERS.md](FINAL_RELEASE_BLOCKERS.md)

---

## Commercial Readiness Score & Classification

- **Commercial Readiness Score:** **96 / 100**
- **Final Classification:** **READY FOR STAGING PROVISIONING & CONTROLLED PILOT — BLOCKED FROM PRODUCTION LAUNCH BY EXTERNAL CREDENTIALS & HARDWARE MATRIX**

> **Honest Assessment:** All source-code, dependency-security (`next@^16.4.6`, zero high/critical prod advisories), media-reservation/cleanup (`0003_media_reservations`), Android SDK 36 target upgrade, fail-closed Android signing/endpoint guards, full-stack live Chromium Playwright E2E, destructive PostgreSQL 16 + media SHA-256 DR verification, and CI workflow fixes have been implemented and verified. Production switch-on remains explicitly gated on external operator credentials (GCP project/billing/WIF/Secret Manager/Vertex AI/Stripe/SMTP + Google Play production upload keystore & `PROD_API_BASE_URL`) and physical Android 13–16 device execution ([FINAL_RELEASE_BLOCKERS.md](FINAL_RELEASE_BLOCKERS.md), [docs/14-android-device-testing-checklist.md](docs/14-android-device-testing-checklist.md)).

---

## 1. Original Audit Issues & Final Remediation Summary (`a170e88..HEAD`)

1. **GitHub Actions CI Failures (`.github/workflows/ci.yml`, run `43661002755`):** Fixed `test_postgres_backup_and_restore_roundtrip` in `services/api/tests/test_ai_durable_jobs.py` to use `pg_commands.POSTGRES_BIN_PATH` and `urlsplit`/`urlunsplit` (preserving Unix socket query strings on Linux runners); upgraded CI to `actions/setup-java@v5`, `android-actions/setup-android@v4` (`platform-tools`, `build-tools;36.0.0`), enforced `npm audit --omit=dev --audit-level=high` + full advisory reporting, added `bash -n infra/scripts/*.sh`, fail-closed `bundleRelease` guard verification, and signed `staging` APK/AAB + `build-metadata.json` upload.
2. **Android Target SDK Upgrade (`targetSdk = 36`):** Upgraded `apps/mobile/app/build.gradle.kts` from `targetSdk = 35` to `targetSdk = 36` (`compileSdk = 37`, `minSdk = 26`). Audited Android 13–16 behaviors across notifications, WorkManager background execution, app-private media storage, edge-to-edge insets, zero location permissions, and HTTPS transport rules ([docs/14-android-device-testing-checklist.md](docs/14-android-device-testing-checklist.md)).
3. **Android Release Endpoints, Fail-Closed Signing & Metadata:** Removed placeholder `.example.com` fallbacks; separated `debug` (`dev`), `staging` (`com.sitediary.mobile.staging`), and `release` (`prod`) API endpoints with `requireValidHttpsEndpoint` failing closed on missing/HTTP/loopback/`.example.*` domains; enforced `GradleException` when `ANDROID_KEYSTORE_*` secrets are missing; added `generateReleaseMetadata` outputting `build-metadata.json` ([docs/15-android-release-signing.md](docs/15-android-release-signing.md)).
4. **Next.js & PostCSS Dependency Vulnerabilities:** Upgraded `apps/web` to `next@^16.4.6` & `eslint-config-next@^16.4.6`, migrated `src/middleware.ts` -> `src/proxy.ts`, and tightened CI `npm audit --omit=dev --audit-level=high` so High/Critical production advisories block builds (`found 0 vulnerabilities`).
5. **Media Upload Reservations & Auditable Orphan Cleanup:** Added `media_reservations` and `media_cleanup_runs` (`0003_media_reservations.py`), `POST /v1/media/reservations`, strict target/reservation ownership validation on `/v1/media/upload-url`, immutable keys + MIME/magic-byte/size/replay/overwrite protections on `/v1/media/complete`, auditable cleanup service + CLI `app.jobs.media_cleanup`, and Android `MediaUploader.kt` reservation support.
6. **Live GCP Staging Verification:** Audited `infra/scripts/deploy-gcp.sh` and [docs/11-gcp-deployment-and-secrets.md](docs/11-gcp-deployment-and-secrets.md) (`CLEANUP_JOB`, `CLOUD_TASKS_HANDLER_URL=${API_URL}`, Secret Manager, WIF). Execution against live GCP remains **BLOCKED BY EXTERNAL CREDENTIALS**.
7. **Backup & Disaster Recovery Verification:** Hardened `infra/scripts/verify-backup-restore.sh` (`urllib.parse` URL parsing, `psql` flag ordering, streaming `tar` + sorted SHA-256 media parity verification) and executed a destructive Postgres 16 + media DR drill verifying identical database state (`0003_media_reservations`) and JPEG SHA-256 through a freshly booted FastAPI application.
8. **Full-Stack Web E2E & Runtime Bug Fixes:** Live Playwright Chromium testing against Postgres + FastAPI + Next.js caught and drove fixes for two real bugs:
   - Extracted dynamic request-scoped CSP generation (`apps/web/src/lib/csp.ts`, applied in `src/proxy.ts` + `next.config.ts`) to keep `https:`-only media policies in production while permitting explicit local loopback API origins (`127.0.0.1` / `localhost`) locally.
   - Fixed `PATCH /v1/logs/{log_id}` (`services/api/app/api/routes/logs.py`) so editing `notes` sets `edited_by_human = True` (unless explicitly overridden), ensuring Web `Edited` badges and PDF export pills persist across reloads.

---

## 2. Files Created & Modified Since Audited Commit (`a170e88..HEAD`)

- **Root, CI & Reports:** `.github/workflows/ci.yml`, `.gitignore`, `DEPLOY.md`, `README.md`, `RELEASE_NOTES.md`, `FINAL_COMMERCIAL_READINESS_REPORT.md`, `FINAL_RELEASE_BLOCKERS.md` *(new)*
- **Docs (`docs/`):** `06-media-security-and-storage.md`, `11-gcp-deployment-and-secrets.md`, `12-backup-restore-and-dr.md`, `14-android-device-testing-checklist.md` *(new)*, `15-android-release-signing.md` *(new)*
- **Infra (`infra/scripts/`):** `deploy-gcp.sh`, `verify-backup-restore.sh`
- **Backend (`services/api/`):**
  - Migrations & Models: `alembic/versions/0003_media_reservations.py` *(new)*, `app/db/models.py`, `app/schemas/media.py`, `app/core/config.py`
  - Routes & Services: `app/api/deps.py`, `app/api/routes/{logs,media,permits,sync,system}.py`, `app/services/storage.py`, `app/services/media_cleanup.py` *(new)*, `app/jobs/media_cleanup.py` *(new)*
  - Tests: `tests/{test_ai_durable_jobs,test_conftest_and_edge_cases,test_media_extraction_reports,test_media_security}.py`
- **Web (`apps/web/`):**
  - Dependencies & Config: `package.json`, `package-lock.json`, `eslint.config.mjs`, `next-env.d.ts`, `next.config.ts`, `tsconfig.json`
  - Proxy, CSP & Components: `src/proxy.ts` *(replaced deleted `src/middleware.ts`)*, `src/lib/csp.ts` *(new)*, `src/lib/pdf/photo-fetcher.ts`, `src/components/{organization/organization-view,project/permit-modal,project/project-dashboard-view,ui/photo-lightbox}.tsx`
  - Tests & E2E: `src/lib/__tests__/csp.test.ts` *(new)*, `playwright.config.ts` *(new)*, `e2e/commercial-readiness.spec.ts` *(new)*
- **Android (`apps/mobile/`):** `app/build.gradle.kts`, `app/src/main/java/com/sitediary/mobile/data/remote/SiteDiaryApi.kt`, `app/src/main/java/com/sitediary/mobile/data/remote/dto/MediaDtos.kt`, `app/src/main/java/com/sitediary/mobile/data/sync/MediaUploader.kt`, `app/src/test/java/com/sitediary/mobile/data/sync/SyncEngineTest.kt`

---

## 3. Latest Verified Command & Test Matrix

| Component | Command | Observed Result |
|---|---|---|
| Backend Lint | `services/api`: `uv run ruff check .` | **Passed** (`All checks passed!`) |
| Backend Typecheck | `services/api`: `uv run mypy .` | **Passed** (`Success: no issues found in 65 source files`) |
| Backend Security Audit | `services/api`: `uvx pip-audit --local` | **Passed** (`No known vulnerabilities found`) |
| Backend Test Suite | `services/api`: `USE_MOCK_GEMINI=true uv run pytest -ra --tb=short` | **Passed** (`35 passed, 1 warning in 40.61s` — Starlette `httpx` deprecation warning in `.venv`) |
| Web Prod Dep Audit | `apps/web`: `npm audit --omit=dev --audit-level=high` | **Passed** (`found 0 vulnerabilities`) |
| Web Full Dep Report | `apps/web`: `npm audit` | **0 high / 0 critical**; reports `8` moderate dev-only advisories (`GHSA-g3hv-75wg-m249` in `minimatch` via `eslint-config-next` -> `@typescript-eslint/typescript-estree`) |
| Web Typecheck & Lint | `apps/web`: `npm run typecheck && npm run lint` | **Passed** (`tsc` 0 errors; `eslint` 0 errors, 2 non-blocking warnings in `bff-client.ts`, `download-pdf.ts`) |
| Web Unit Tests | `apps/web`: `npm test` (`vitest run`) | **Passed** (`Test Files 7 passed (7)`, `Tests 42 passed (42)`) |
| Web Production Build | `apps/web`: `NEXT_PUBLIC_DEMO_MODE=false npm run build` | **Passed** (`15/15` static routes + `ƒ Proxy (Middleware)`) |
| Web Full-Stack E2E | `apps/web`: `npx playwright test --reporter=list` (live Postgres + FastAPI `:8000` + Next `:3000`) | **Passed** (`1 passed (19.3s)` — signup, invites, RBAC 403s, projects, offline photo reserve/sync/render, lightbox, note edit `Edited` persistence, permit CRUD, real `%PDF-` export, billing, team tab, session redirect `?next=`, zero console/page errors) |
| Android Unit & Lint | `apps/mobile`: `.\gradlew.bat testDebugUnitTest lintDebug --no-daemon --console=plain` | **Passed** (`BUILD SUCCESSFUL in 32s`; `TOTAL: tests=34 failures=0 errors=0 skipped=0` across `8` classes; 0 lint errors) |
| Android Fail-Closed Guard | `apps/mobile`: `.\gradlew.bat bundleRelease --no-daemon --console=plain` *(no `PROD_API_BASE_URL` / keystore)* | **Passed (Fail-Closed)**: `GradleException: Production Release builds require an explicit HTTPS API endpoint` |
| Android Staging Signed APK/AAB | `apps/mobile`: `assembleStaging bundleStaging generateReleaseMetadata` *(ephemeral PKCS12, shredded after test)* | **Passed**: `app-staging.apk` (`3,527,762` B) `apksigner` v2 `Verifies`; `app-staging.aab` (`7,244,382` B) `jarsigner` `jar verified.`; `build-metadata.json` (`targetSdk: 36`, `productionReady: false`); zero keystores in git |
| DR Backup & Restore | `infra/scripts/verify-backup-restore.sh` + live API restore drill | **Passed**: `rev=0003_media_reservations, orgs=1, users=1, projects=1, logs=1, photos=1`, `Media backup/restore verified (1 files, SHA-256 identical)`, restored API served identical JPEG (`SHA-256 98888c2bd...f1a9`) |
| Infra Shell Scripts | `infra/scripts/*.sh`: `bash -n` | **Passed** (`5/5` scripts valid) |

---

## 4. Remaining External Blockers & Untested Hardware Scope

1. **External Cloud Credentials Required (`BLOCKED BY EXTERNAL CREDENTIALS`):**
   - Google Cloud Project ID, billing account, Cloud SQL PostgreSQL 16, Cloud Storage bucket, Artifact Registry, Secret Manager, Cloud Tasks, Cloud Scheduler, Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`), GitHub WIF provider/SA, Stripe keys/prices, SMTP credentials, and optional Firebase `google-services.json`.
   - Google Play Console upload keystore (`ANDROID_KEYSTORE_*`) and canonical HTTPS production domain (`PROD_API_BASE_URL`) for signed `release` (`prod`) AAB and live production API authentication.
2. **Physical Device Hardware QA (`NOT TESTED`):**
   - Interactive hardware/AVD verification across Android 13, 14, 15, and 16 (zero physical `adb` devices or AVD system images installed in this environment). See [docs/14-android-device-testing-checklist.md](docs/14-android-device-testing-checklist.md).
3. **Database Migrations Preserved:**
   - `contracts/schema.sql` and `services/api/app/db/initial_schema.sql` remain byte-identical; additive schema changes live cleanly in `0002_commercial_saas_hardening.py` and reversible `0003_media_reservations.py`.
