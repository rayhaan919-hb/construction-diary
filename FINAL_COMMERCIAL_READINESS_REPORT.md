# Final Commercial Readiness Report — Construction Diary (`site-diary`)

**Report Date:** 2026-11-15  
**Repository:** `https://github.com/rayhaan919-hb/construction-diary.git` (`main`)  
**Commercial Readiness Baseline:** Follows `1bf6839` -> `COMMERCIAL_READINESS_AUDIT.md` (`e44ce99`) -> Backend hardening (`f1cfe65`) -> Mobile, Web, Infra & Legal/Ops hardening (`364a673` + final CI/Release/Legal commit).

---

## Commercial Readiness Score & Classification

- **Commercial Readiness Score:** **91 / 100**
- **Final Classification:** **READY FOR CONTROLLED CUSTOMER PILOT**

> Rationale: All source-code security vulnerabilities, multi-tenant isolation boundaries, offline-first synchronization data-loss bugs, fail-closed secret management, durable AI job queues, mobile release hardening (`assembleRelease`/`bundleRelease`), CI/CD security/build pipelines, and legal/technical documentation have been implemented and verified locally. Final promotion to `READY FOR COMMERCIAL RELEASE` requires provisioning live external cloud environments (GCP project + Cloud SQL + GCS + Vertex AI + Secret Manager + WIF), configuring a production Android release signing keystore & Firebase project, running live interactive browser E2E checks, and addressing the upstream `next`/`postcss` major-version bump advisory (`next@16`).

---

## 1. Original Problems Identified (`COMMERCIAL_READINESS_AUDIT.md`)

1. **Cross-Tenant / Cross-Project Storage URI Injection & Overwrites:** Arbitrary `local://` and `gs://` URIs accepted in sync/permits routes; `/v1/media/upload-url` lacked record ownership verification, deterministic keys allowed silent overwrites, and uploads lacked magic-byte, byte-size, and ticket-replay defenses.
2. **Absence of Organization Multi-Tenancy:** No `organizations` table or tenant boundary; global email enrollment leaked account existence and escalated roles.
3. **Production-Unsafe Secret Defaults:** Known development secrets (`JWT_SECRET`, `MEDIA_URL_SIGNING_SECRET`, `SEED_*_PASSWORD`) booted silently without startup checks; no GCP Secret Manager integration.
4. **Silent Offline Voice Note Upload Loss (`apps/mobile`):** `SyncEngine` cleared `syncDirty` and let immediate `pullAndBackfill()` overwrite `audioUploadStatus = "PENDING"` with `"NONE"`; interrupted project backfills lost in-memory cursors; logout/401 left Room rows/files intact; `AppPreferences.clearAllSettingsOnLogout()` left encrypted auth/FCM tokens intact; push `CONFLICT` cleared `syncDirty = 0`; remote photo tombstones left local photo files and DB rows.
5. **Android Release & Transport Exposure:** Cleartext HTTP permitted globally, plaintext `SharedPreferences` tokens, unguarded dev API URL fallback on release builds, missing R8/backup/Arabic resource completeness.
6. **Fragile In-Process AI Extraction:** Used FastAPI `BackgroundTasks` instead of durable DB + Cloud Tasks execution, risking silent loss on container restart.
7. **Web BFF Security & SaaS Gaps:** Missing CSP/XFO/security headers, CSRF origin validation, refresh-token serialization, fail-open owner UI guards, SSRF guards on report photo fetches, and self-service registration/org/billing/audit flows.
8. **Deployment, Legal & CI Gaps:** Missing automated GCP scripts, backup/restore drills, Gitleaks/dependency scanning, Android release build CI step, legal policies, and complete readiness reporting.

---

## 2. Problems Fixed

- **Media Upload Security:** Added single-use DB `UploadTicket` records bound to `(user, project, kind, object_id)` with expiration checks, SHA-256 verification, immutable UUID object paths, traversal blocking, byte-size limits (`25 MB`), and magic-byte validation (`services/api/app/services/media_security.py`, `app/api/routes/media.py`), plus regression tests in `test_media_security.py`.
- **Auth & Tenant Isolation:** Added Argon2id password hashing with rehash upgrades, HS256 JWTs (`iss`/`aud`), refresh rotation + reuse-family revocation, login lockouts & rate limits, password resets, `organizations`/`organization_members`/`organization_invitations` isolation, plan quotas, Stripe checkout + HMAC replay-safe webhooks, and `audit_logs` (`saas.py`, `auth.py`, `0002_commercial_saas_hardening.py`).
- **Config & Secrets:** Added `validate_runtime_configuration()` fail-closed checks for `staging`/`production` and native `sm://` / `GCP_SECRET_MANAGER_ENABLED` Secret Manager resolution (`config.py`, `secrets.py`).
- **Offline Sync & Mobile Security:** Preserved offline audio queue across sync cycles, persisted backfill cursors (`sync_cursors`), wiped Room + media + encrypted `authPrefs` cleanly on logout/401 (`clearAllSettingsOnLogout`), preserved dirty edits on `CONFLICT` (`markSyncConflictIfSeqMatches` + `CONFLICT_PENDING`), deleted tombstoned local photos + Room entries, enforced Keystore `AES/GCM/NoPadding` token storage, disabled release cleartext traffic, enforced external `https://` `RELEASE_API_BASE_URL` on Android release builds, added full Arabic (`values-ar`) + Urdu (`values-ur`) strings, and verified R8 `assembleRelease` + `bundleRelease`.
- **Durable AI Pipeline:** Implemented `extraction_jobs` with unique active constraint, `FOR UPDATE SKIP LOCKED` workers, stale lease recovery, retries, Pydantic output validation, and Cloud Tasks dispatch (`extraction_worker.py`, `ai_extractor.py`).
- **Web BFF & SaaS Portal:** Added CSRF origin checks (`csrf.ts`), CSP/XFO headers (`next.config.ts`), SSRF IP/DNS blocking (`photo-fetcher.ts`), `/register`, `/invite`, `/forgot-password`, `/reset-password`, `/organization`, and seeded `NEXT_PUBLIC_DEMO_MODE=true`.
- **Legal, CI/CD & Infra:** Added 7 legal/commercial markdown policies (`docs/legal/*`, `RELEASE_NOTES.md`), 13 technical guides (`docs/01`–`13`), `SECURITY.md`, 5 GCP scripts (`infra/scripts/*.sh`), WIF CD (`cd.yml`), and CI secret/dependency/release checks (`ci.yml`).

---

## 3. Files Modified (Cumulative `1bf6839..HEAD`)

- **Root & Workflows:** `.env.example`, `.github/workflows/ci.yml`, `DEPLOY.md`, `README.md`, `docker-compose.yml`
- **Backend (`services/api/`):** `Dockerfile`, `requirements-dev.txt`, `app/main.py`, `app/api/deps.py`, `app/api/routes/{auth,logs,media,permits,projects,sync,system}.py`, `app/core/{config,errors}.py`, `app/db/{models,session}.py`, `app/jobs/permit_alerts.py`, `app/schemas/{auth,logs,media,permits,projects,sync}.py`, `app/scripts/seed.py`, `app/services/{ai_extractor,auth,extraction_worker,reports,storage}.py`, `tests/{conftest,test_ai_extractor,test_auth,test_media_extraction_reports,test_projects_permits,test_sync}.py`
- **Web (`apps/web/`):** `Dockerfile`, `next.config.ts`, `src/middleware.ts`, `src/app/login/page.tsx`, `src/app/api/auth/{login,logout,password}/route.ts`, `src/app/api/bff/[...path]/route.ts`, `src/app/api/reports/[projectId]/[date]/pdf/route.ts`, `src/components/layout/portal-header.tsx`, `src/components/portfolio/portfolio-view.tsx`, `src/components/project/{log-note-card,permit-modal,permits-tile,project-dashboard-view,team-settings-panel,timeline-section}.tsx`, `src/components/ui/modal.tsx`, `src/lib/{bff-path,config,jwt,server-api,types}.ts`, `src/lib/pdf/{daily-report-pdf,photo-fetcher}.ts`, `src/lib/__tests__/{auth-routes,bff-proxy,pdf-report}.test.ts`
- **Mobile (`apps/mobile/`):** `app/build.gradle.kts`, `app/proguard-rules.pro`, `app/src/main/AndroidManifest.xml`, `app/src/main/res/xml/network_security_config.xml`, `SiteDiaryDatabase.kt`, `PermitDao.kt`, `SiteLogDao.kt`, `SiteLogPhotoDao.kt`, `SyncCursorDao.kt`, `SiteLogEntity.kt`, `AudioRecorderController.kt`, `LocalMediaFileManager.kt`, `FcmTokenManager.kt`, `SiteDiaryFirebaseMessagingService.kt`, `AppPreferences.kt`, `SiteDiaryApi.kt`, `AuthDtos.kt`, `MediaDtos.kt`, `SiteLogDtos.kt`, `AuthRepository.kt`, `SiteDiaryRepository.kt`, `MediaUploader.kt`, `SyncEngine.kt`, `DatabaseModule.kt`, `SiteDiaryNavHost.kt`, `LogDetailScreen.kt`, `LogDetailViewModel.kt`, `PermitsScreen.kt`, `PermitsViewModel.kt`, `ProjectsScreen.kt`, `RecordNoteScreen.kt`, `RecordNoteViewModel.kt`, `Color.kt`, `SyncEngineTest.kt`, `FakeDaos.kt`

---

## 4. New Files Created (Cumulative `1bf6839..HEAD`)

- **Audit, Release & Security:** `COMMERCIAL_READINESS_AUDIT.md`, `FINAL_COMMERCIAL_READINESS_REPORT.md`, `RELEASE_NOTES.md`, `SECURITY.md`, `.github/workflows/cd.yml`
- **GCP Automation (`infra/scripts/`):** `setup-gcp.sh`, `deploy-gcp.sh`, `backup-db.sh`, `restore-db.sh`, `verify-backup-restore.sh`
- **Technical Guides (`docs/`):** `01-architecture-overview.md` through `13-onboarding-and-troubleshooting.md`
- **Legal & Licensing (`docs/legal/`):** `PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`, `DATA_PROCESSING_POLICY.md`, `COOKIE_POLICY.md`, `ACCEPTABLE_USE_POLICY.md`, `COMMERCIAL_LICENSING.md`
- **Backend (`services/api/`):** `alembic/versions/0002_commercial_saas_hardening.py`, `app/api/routes/saas.py`, `app/core/{logging_config,permissions,rate_limit,secrets}.py`, `app/schemas/saas.py`, `app/services/{audit,media_security,saas}.py`, `tests/{test_ai_durable_jobs,test_auth_and_config_security,test_media_security,test_saas_multitenancy_audit}.py`
- **Web (`apps/web/`):** `.env.example`, `src/app/{error,not-found}.tsx`, `src/app/{forgot-password,invite,organization,register,reset-password}/page.tsx`, `src/app/api/auth/{accept-invite,register,password-reset/request,password-reset/confirm}/route.ts`, `src/components/organization/organization-view.tsx`, `src/lib/{csrf,demo-data}.ts`, `src/lib/pdf/download-pdf.ts`, `src/lib/__tests__/demo-mode.test.ts`
- **Mobile (`apps/mobile/`):** `app/schemas/.../2.json`, `src/debug/res/xml/network_security_config.xml`, `ConnectivityObserver.kt`, `OfflineStatusBanner.kt`, `ic_launcher_sitediary.xml`, `values-ar/strings.xml`, `values-ur/strings_extra.xml`, `values/strings_extra.xml`, `backup_rules.xml`, `data_extraction_rules.xml`, `FcmTokenManagerTest.kt`, `SecurityRepositoryAndViewModelTest.kt`

---

## 5. Security Improvements

- Argon2id password hashes, constant-time/dummy timing equalization, account lockout, and rate limiting.
- Short-lived HS256 JWTs + single-use rotating refresh tokens with reuse-family revocation.
- Single-use DB-backed `UploadTicket` media authorization, MIME + magic-byte checks, path-traversal prevention, and immutable UUID keys.
- Organization-scoped tenancy, dual-layer RBAC (`ORG_*` + project roles), and append-only `audit_logs`.
- Web BFF HttpOnly cookies, CSRF origin/header verification, CSP/XFO headers, and PDF SSRF IP/DNS filter.
- Android Keystore `AES/GCM/NoPadding` preferences, complete logout wipe, release cleartext disabled, and HTTPS `RELEASE_API_BASE_URL` enforcement.
- Secret redaction filter in structured logs and fail-closed production startup config validation.

---

## 6. Backend Improvements

- Consistent RFC 7807 `ProblemException` handlers with request IDs.
- 25 MB upload and configurable request body caps.
- Pagination across projects, logs, members, and audit logs.
- `/healthz`, `/readyz` (live DB + storage probe), and `/metrics` endpoints plus graceful lifespan shutdown.
- Durable `extraction_jobs` queue with lease locks, retry backoff, and Cloud Tasks integration.

---

## 7. Android Improvements

- Fixed offline voice-note overwrite, backfill cursor loss on interruption, 401 shared-device cleanup, logout token persistence, conflict preservation (`CONFLICT_PENDING`), and remote photo tombstone cleanup (Room + disk).
- Added remote M4A playback support, offline status banner, Arabic (`values-ar`) & Urdu (`values-ur`) RTL coverage, R8/Proguard rules, release URL build guard, and 34 JUnit tests + `lintDebug` + `assembleRelease` / `bundleRelease` verification.

---

## 8. Web Improvements

- Complete SaaS workspace flows: `/register`, `/invite`, `/forgot-password`, `/reset-password`, `/organization` (profile, subscription tiers, quota usage, Stripe checkout trigger, member/invite management, audit log pagination, JSON export, suspend/delete).
- Timeline search/filters, inline log editing/deletion, audio playback, accessible modals, custom error/404 pages, bilingual RTL PDF generation, and offline demo mode (`NEXT_PUBLIC_DEMO_MODE=true`).

---

## 9. Database Changes

- Kept `contracts/schema.sql` byte-identical to `services/api/app/db/initial_schema.sql` (verified by `test_schema_and_health.py`).
- Added forward/reversible Alembic migration `0002_commercial_saas_hardening.py` introducing `organizations`, `organization_members`, `organization_invitations`, `audit_logs`, `billing_events`, `upload_tickets`, `extraction_jobs`, foreign keys, composite tenant indexes, and quota check constraints.

---

## 10. Deployment & CI/CD Changes

- Non-root Python & Node Dockerfiles with `/healthz` and `/api/health` container healthchecks; `127.0.0.1` bindings in `docker-compose.yml`.
- Executable GCP provisioning, deployment, backup, restore, and DB verification scripts (`infra/scripts/*.sh`).
- CI workflow (`ci.yml`) running Gitleaks secret scanning, `npm audit`, `pip-audit`, backend `ruff`/`mypy`/`pytest`, web `typecheck`/`lint`/`vitest`/`next build`, and Android `testDebugUnitTest`/`lintDebug`/`assembleRelease`/`bundleRelease`.
- Environment-gated CD workflow (`cd.yml`) using GCP Workload Identity Federation.

---

## 11. Test & Verification Results (Observed After Edits)

| Component | Command | Observed Outcome |
|---|---|---|
| Backend Lint | `services/api`: `uv run ruff check .` | **Passed** (`All checks passed!`) |
| Backend Typecheck | `services/api`: `uv run mypy .` | **Passed** (`Success: no issues found in 62 source files`) |
| Backend Security Audit | `services/api`: `uvx pip-audit --local` | **Passed** (`No known vulnerabilities found`) |
| Backend Test Suite | `services/api`: `USE_MOCK_GEMINI=true uv run pytest --tb=short` | **Passed** (`32 passed, 1 warning` — Starlette `httpx` deprecation warning in `.venv`) |
| Web Dependency Audit | `apps/web`: `npm audit --omit=dev --audit-level=critical` | **Passed** (`0` critical; `2` upstream advisories via `next` transitive `postcss`, requiring `next@16` major bump) |
| Web Typecheck | `apps/web`: `npm run typecheck` | **Passed** (`0` errors) |
| Web Lint | `apps/web`: `npm run lint` | **Passed** (`0` errors, `0` warnings) |
| Web Test Suite | `apps/web`: `npm test` | **Passed** (`6` test files, `39` tests passed) |
| Web Production Build | `apps/web`: `npm run build` | **Passed** (`16/16` pages built) |
| Android Debug Tests & Lint | `apps/mobile`: `.\gradlew.bat testDebugUnitTest lintDebug --no-daemon --console=plain` | **Passed** (`BUILD SUCCESSFUL`: `34` tests across `8` test classes, `0` lint errors) |
| Android Release APK & AAB | `apps/mobile`: `RELEASE_API_BASE_URL=https://api.sitediary.example.com .\gradlew.bat assembleRelease bundleRelease --no-daemon --console=plain` | **Passed** (`BUILD SUCCESSFUL`, R8 shrinking + release APK & AAB generated) |
| Android Release Dev-URL Guard | `apps/mobile`: `.\gradlew.bat assembleRelease --no-daemon --console=plain` (no `RELEASE_API_BASE_URL`) | **Passed (Fail-Closed)**: `Release builds require an external HTTPS API_BASE_URL or RELEASE_API_BASE_URL` |
| Infra Shell Scripts | `infra/scripts/*.sh`: `bash -n` | **Passed** (all `5` scripts valid) |

---

## 12. Remaining Limitations

1. Live interactive headless/real-device browser E2E checks across desktop, tablet, and mobile viewports were not executed against a running full-stack Cloud Run/Postgres deployment.
2. Android instrumentation (`androidTest`) on a physical device and Play Console release signing were not run locally (no physical device or production keystore mounted).
3. `apps/web` `npm audit --omit=dev` flags 1 high / 1 moderate transitive `postcss` advisory pinned under `next@15.5.29` (fix requires breaking `next@16` upgrade).

---

## 13. External Services Requiring Credentials

- **Google Cloud Platform:** Project ID, billing account, Cloud SQL PostgreSQL 16, GCS bucket, Artifact Registry, Secret Manager, Cloud Tasks, Cloud Scheduler, and GitHub WIF provider/service account.
- **Vertex AI / Gemini (`GOOGLE_GENAI_USE_VERTEXAI=true`):** Production Vertex AI access (evaluated locally with `USE_MOCK_GEMINI=true`).
- **Firebase Cloud Messaging:** Optional `apps/mobile/app/google-services.json` and backend `FCM_PROJECT_ID` / credentials.
- **Stripe:** Live `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and plan price IDs (`STRIPE_PRICE_*`).
- **SMTP:** Production transactional mailer (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`) for password reset emails.
- **Android Play Signing:** Production `.jks` keystore and GitHub Actions signing secrets (`ANDROID_KEYSTORE_*`).

---

## 14. Manual Configuration Still Required

1. Provision GCP project resources via `infra/scripts/setup-gcp.sh` and store real DB/Stripe/SMTP credentials in Secret Manager.
2. Configure GitHub Environment variables (`GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`) and protected reviewer approvals on the `production` GitHub Environment.
3. Run `infra/scripts/deploy-gcp.sh`, configure Cloud Scheduler cron (`0 7 * * *` `Asia/Karachi`), and execute a staging `restore-db.sh` / `verify-backup-restore.sh` drill against live Cloud SQL.
4. Provide company entity contact/address placeholders if required for specific jurisdictional filings in `docs/legal/*`.

---

## 15. Recommended Next Steps

1. Run `infra/scripts/setup-gcp.sh` and `deploy-gcp.sh` in a staging GCP project, populate `google-services.json`, and run an end-to-end smoke test across real Android APK + Web Portal + Vertex AI audio/photo/PDF extraction.
2. Execute `infra/scripts/verify-backup-restore.sh` in staging and complete a cross-browser responsive viewport QA sweep before onboarding external pilot tenants.
3. Schedule a planned upgrade from `next@15.5.29` to `next@16.x` once validated with Next.js App Router dependencies to clear the upstream transitive `postcss` advisory.
