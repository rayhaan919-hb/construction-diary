# Commercial Readiness Audit — Construction Diary (`site-diary`)

**Audit Date:** 2026-11-15  
**Repository:** `https://github.com/rayhaan919-hb/construction-diary.git` (post-`1bf6839` baseline)  
**Scope:** Full-stack inspection of `services/api/` (FastAPI, SQLAlchemy, Alembic, AI pipeline, storage, background jobs), `apps/mobile/` (Kotlin, Compose, Room, WorkManager, Hilt, Gradle), `apps/web/` (Next.js 15 App Router, BFF, PDF renderer, Vitest), `contracts/` (`schema.sql`, `api-contract.yaml`), Dockerfiles, `docker-compose.yml`, `DEPLOY.md`, `.github/workflows/ci.yml`, `LICENSE`, and documentation.

---

## Executive Summary & Commercial Release Blockers

While the repository provides a structured multi-platform skeleton (offline-first Android app, Next.js BFF owner portal with A4 bilingual PDF export, FastAPI + PostgreSQL 16 + Alembic backend), **it is NOT currently ready for commercial release**. Critical security vulnerabilities, silent offline data loss bugs, missing multi-tenant isolation, fragile in-process background execution, plaintext mobile token storage, and incomplete deployment/compliance artifacts block production customer onboarding.

### Top Commercial Release Blockers
1. **Cross-Tenant / Cross-Project Storage URI Injection & Media Overwrite (`services/api/app/api/routes/media.py`, `sync.py`, `permits.py`, `storage.py`)**: Any active supervisor can submit arbitrary `local://` or `gs://` storage URIs for another project/tenant or request `/upload-url` for another user's `object_id` and overwrite their media, without file size binding, MIME/magic-byte verification, or single-use upload tickets.
2. **Absence of Organization / Company Multi-Tenancy & Safe Member Enrollment (`contracts/schema.sql`, `routes/projects.py`)**: No `organizations` table or `organization_id` boundary exists. Any project `OWNER` can unilaterally enroll users from unrelated companies via email lookup, enumerate registered accounts, and inherit/escalate global roles.
3. **Production-Unsafe Secret Defaults Without Startup Validation (`services/api/app/core/config.py`, `DEPLOY.md`)**: Hardcoded development secrets (`JWT_SECRET`, `MEDIA_URL_SIGNING_SECRET`, `SEED_*_PASSWORD`) boot silently in production; `USE_MOCK_GEMINI=True` defaults to mock mode.
4. **Silent Offline Voice Note Upload Drop (`apps/mobile/.../SyncEngine.kt:566`)**: Creating a voice log offline pushes `audio_uri = null` and then `pullAndBackfill()` overwrites local `audioUploadStatus = "PENDING"` to `"NONE"` *before* `MediaUploadWorker` executes.
5. **Interrupted Project Backfill Data Loss & 401 Cross-User Leak (`SyncEngine.kt:195,240-276`, `TokenRefreshAuthenticator.kt:87-91`)**: Newly assigned project backfills are tracked only in memory while `GLOBAL_CURSOR_KEY` is already committed; 401 refresh failures wipe tokens but leave Room tables, local media, and cursors intact for the next user.
6. **Android Cleartext Traffic & Plaintext Credential Storage (`network_security_config.xml:4`, `AppPreferences.kt:37`)**: Global `cleartextTrafficPermitted="true"`, plaintext `SharedPreferences` tokens with async `.apply()` race on rotating refresh tokens, and unconfigured release signing / R8 obfuscation (`app/build.gradle.kts:43-51`).
7. **Fragile In-Process AI Processing & Audio-Only Pipeline (`extraction_worker.py`, `ai_extractor.py`, `main.py`)**: Relies on ephemeral FastAPI `BackgroundTasks` instead of a durable DB + Cloud Tasks queue, blocks AnyIO worker threads with `time.sleep`, and lacks extraction support for diary text, site photos, PDFs, or permit documents.
8. **Web BFF Security & SaaS Gaps (`apps/web/`)**: Missing HTTP security headers (`CSP`, `HSTS`, `X-Frame-Options`), missing CSRF `Origin` checks on mutating routes, unverified JWT decode causing redirect loops, refresh-token concurrency race, fail-open `isOwner` UI guard (`!user || user.role === "OWNER"`), and missing SaaS tenant/subscription/audit/legal pages.

---

## 1. Critical Vulnerabilities

| ID | Component | Location | Finding | Impact |
|---|---|---|---|---|
| **CRIT-01** | Backend Media & Sync | `routes/sync.py` (`L162,179,265,301,395,412`), `routes/permits.py` (`L94,135`), `storage.py` (`L102-249`) | `document_photo_uri`, `audio_uri`, `storage_uri` accepted verbatim from client payloads with zero `projects/{project_id}/` prefix or backend ownership validation. `sign_get_url` signs any `local://` or `gs://` URI. | Cross-project/cross-tenant media exfiltration and unauthorized Gemini processing via SSRF-like storage URI injection. |
| **CRIT-02** | Backend Auth & Multi-Tenancy | `schema.sql` (`L32-98`), `routes/projects.py` (`L265-355`) | No `organizations` isolation; `invite_member` queries global users by email, auto-enrolls without consent, enumerates emails via `temporary_password`, and assigns target user's global role (`OWNER`) instead of scoped project role. | Cross-company data access, account enumeration, and privilege escalation. |
| **CRIT-03** | Backend Config & Secrets | `core/config.py` (`L31,37,50,67-69`), `main.py` (`L50-76`), `.env.example` | Default `JWT_SECRET`, `MEDIA_URL_SIGNING_SECRET`, `SEED_*_PASSWORD`, `USE_MOCK_GEMINI=True`; no startup assertion rejecting dev secrets or missing production config. | Forged JWTs and forged signed media URLs in misconfigured deployments. |
| **CRIT-04** | Backend Media Upload | `routes/media.py` (`L32-62,262-288`), `storage.py` (`L24-26,138-260`) | `/upload-url` does not verify record ownership; deterministic keys (`projects/{id}/{kind}/{object_id}.{ext}`) allow silent overwrites; `byte_size` ignored; no GCS size limit, no single-use ticket DB record, no magic-byte/MIME validation. | Any project member can overwrite another user's evidence, replay signed upload URLs, or upload executable/oversized payloads. |
| **CRIT-05** | Android Offline Sync | `SyncEngine.kt` (`L566`, `L387-406`), `SiteLogDao.kt` (`L56`) | `pushPendingChanges()` sets `syncDirty=0` on new audio logs; immediate `pullAndBackfill()` overwrites local `audioUploadStatus="PENDING"` with `"NONE"` before `MediaUploadWorker` runs. | **100% silent loss of offline field voice note uploads.** |
| **CRIT-06** | Android Backfill & Isolation | `SyncEngine.kt` (`L195,240-276`), `TokenRefreshAuthenticator.kt` (`L87-91`) | In-memory `projectsToBackfill` lost if interrupted after `GLOBAL_CURSOR_KEY` commit; 401 refresh failure clears only `AppPreferences`, leaving Room DB, local media, DataStore, and cursors intact. | Permanent historical data gaps and cross-user local data leakage on shared field devices. |
| **CRIT-07** | Android Transport & Storage | `network_security_config.xml:4`, `AppPreferences.kt:37,72-99` | `<base-config cleartextTrafficPermitted="true" />` in release builds; tokens/user JSON stored in plaintext `SharedPreferences` with async `.apply()` writes. | Cleartext credential/media interception and rotating-refresh-token corruption races (`TOKEN_REUSED`). |
| **CRIT-08** | Web Security & Auth | `apps/web/src/middleware.ts:30-78`, `next.config.ts`, `apps/web/src/app/api/**` | Missing CSP/HSTS/XFO headers; zero CSRF `Origin` checks on cookie-authenticated routes; unverified JWT expiry decode causes `/` <-> `/login` infinite loop; middleware + BFF lack cross-request refresh serialization; `NEXT_PUBLIC_DEMO_MODE` bypasses auth if enabled in prod. | CSRF mutations, clickjacking, accidental auth bypass, and involuntary user lockouts on token rotation. |

---

## 2. Major Bugs & Security Highs

1. **Auth Lifecycle & Brute-Force Gaps (`services/api/app/api/routes/auth.py`, `deps.py`, `schemas/auth.py`)**:
   - No login throttling, IP rate limiting, or progressive account lockout on `/v1/auth/login`.
   - `LoginRequest.password` and `ChangePasswordRequest.new_password` lack `max_length`, exposing Argon2id (`64 MiB`) to multi-MB password CPU/RAM DoS.
   - `change_password` does not revoke active `RefreshToken` chains or bump user `token_version`.
   - `must_change_password` is never enforced server-side in `get_current_user` (or on web `/api/bff/*` & `/api/reports/*/pdf`).
   - Missing password reset flow, session listing, selective session revocation, and `logout-all`; `/logout` does not clean up `DeviceToken` push tokens; `register_device_token` `on_conflict_do_update` lets one user hijack another's `fcm_token`.
   - JWTs lack `iss`, `aud`, `jti`, and `token_version` revocation checks; `_PASSWORD_HASHER.check_needs_rehash` is never executed.
2. **Error/Secret Information Disclosure (`sync.py:194-202,319-327,431-439`, `extraction_worker.py:61-62,97`, `errors.py:138-147`)**:
   - Sync push rejection responses and `site_logs.extraction_error` leak raw exception/SQL messages (`str(exc)`) directly to mobile and web clients.
   - Global 500 handler in `errors.py` catches `Exception` without `logger.exception(...)`, leaving unhandled 500s invisible in server logs.
   - `apps/web/src/lib/server-api.ts:118-121,235-238` leaks internal API hostnames (`err.message`) to browsers, and `server-api.ts:256` lacks `try/catch` causing raw 500s.
3. **In-Process `BackgroundTasks` & AI Pipeline Deficiencies (`extraction_worker.py`, `ai_extractor.py`, `main.py`, `media.py`)**:
   - Uses request-scoped FastAPI `BackgroundTasks` cleanly dropped on Cloud Run shutdown/scale-to-zero; startup recovery runs once without `FOR UPDATE SKIP LOCKED` or stale lease recovery.
   - `time.sleep(min(2 ** (attempt - 1), 8))` inside AnyIO threadpool ties up threads for up to ~187s per failing extraction.
   - Concurrent `sync_push` edits and `extraction_worker` final write lack row locking (`SELECT ... FOR UPDATE`).
   - AI pipeline only transcribes `audio/mp4` (`ai_extractor.py`), ignoring diary descriptions, site photographs, uploaded documents, and permit documents; prompt lives in user `contents` rather than `system_instruction`; output fields lack length/range bounds.
4. **Offline Sync Integrity Bugs (Backend `sync.py` & Android `SyncEngine.kt`/`Workers`)**:
   - Backend `_apply_photo_push` allows attaching photos to soft-deleted `SiteLog`s; `_apply_*_push` ignores `client_updated_at`, permitting zombie resurrection of deleted records and stale overwrites.
   - Android `SyncEngine` swallows `/v1/sync/push` rejections cleanly (`syncDirty=false` with zero UI conflict/error surfacing), omits `PROJECT_DELETED` handling for `SiteLogPhotoEntity`, treats HTTP 400/403/404/422 as infinite retry loops, lacks mutex synchronization across `SyncWorker` / `MediaUploadWorker`, forgets periodic workers in `cancelAllSyncWork()`, omits pending photos from `pendingCount`, and leaves orphaned local files on individual record deletes or audio recorder auto-stop (`MAX_DURATION_MS`).
5. **Web Portal Bugs (`apps/web/`)**:
   - Fail-open owner checks (`const isOwner = !user || user.role === "OWNER"`) in `portfolio-view.tsx:32` & `team-settings-panel.tsx:52`, plus ignoring project-scoped `Member.role`.
   - `handleRetryExtraction` (`project-dashboard-view.tsx:230-251`) never refreshes/polls updated extraction results.
   - `pdf/route.ts:76-110` drops rotated auth cookies from `permitsOutcome`, accepts invalid dates like `2026-99-99`, wraps whole log entries in `<View wrap={false}>` (`daily-report-pdf.tsx:356`), omits non-transcript RTL font support, and uses raw `<a href>` download links with zero loading/error handling.
   - `sanitizeNextPath` (`apps/web/src/app/login/page.tsx:7-12`) allows `/\evil.com` open redirect bypasses.
   - `isSessionCookieSecure()` (`config.ts:13-15`) fails open (`false`) if `SESSION_COOKIE_SECURE` is unset in production.
   - BFF proxy (`bff-path.ts`) proxies every `/v1/*` path including mobile sync/local-media routes and buffers unbounded byte payloads.

---

## 3. Minor Bugs

- `contracts/schema.sql` hardcodes `+ 14` in `permits_with_status`, leaving `Settings.PERMIT_EXPIRING_SOON_DAYS` unused; `permit_alerts` unique constraint blocks re-alerting after a permit is renewed.
- `run_permit_alerts` (`permit_alerts.py`) runs without a job advisory lock, opens new SMTP TLS/OAuth2 `httpx.Client` per recipient, dispatches notifications *before* `db.commit()`, and logs PII (`recipient_email`, `permit_name`) via `ConsoleNotifier`.
- `SiteLogPhotoPush` lacks non-negative/upper bounds on `width`/`height`; `site_log_photos.byte_size` uses signed 32-bit integer.
- `contracts/api-contract.yaml` & backend `StarletteDeprecationWarning` (`httpx` vs `httpx2` with `starlette 1.10.0` `TestClient`).
- Android: `AudioRecorderController` leaks native `MediaRecorder` if `prepare()`/`start()` throws; `PermitsScreen` uses free-text `issueDate`, unguarded `LocalDate.parse`, non-saveable dialog state (`showExpiryPicker`), no document removal; `LogDetailScreen` shows infinite skeleton if deleted; UTC raw timestamps; `values-ar` missing despite RTL flag; unused `strings.xml` keys while ViewModels hardcode English; yellow/amber accent contrast (`3.19:1`).
- Web: `CreateProjectModal` keeps stale form data on cancel; timezone inputs lack `Intl.DateTimeFormat` check; `PermitModal` skips `issue_date <= expiry_date`; `Modal` lacks focus trap & unique `aria-labelledby`; `error.tsx`/`not-found.tsx` missing; `apps/web/scripts/generate-types.mjs` imports undeclared transitive dependency `js-yaml`.

---

## 4. Missing Commercial & SaaS Functionality

1. **Multi-Tenancy & Company Management (Phase 10)**: No company registration, company profiles, tenant-level isolation (`organization_id`), employee email/link invitations with accept flow, expanded RBAC (`OWNER`, `ADMIN`, `PROJECT_MANAGER`, `SUPERVISOR`, `WORKER`, `VIEWER`), role management UI, subscription tiers/usage quotas, billing integration architecture (configurable Stripe/webhook adapter), account suspension/deletion, or organization data export (JSON/CSV/ZIP).
2. **Audit Logging & Monitoring (Phase 11)**: No immutable `audit_logs` table, structured JSON request/error telemetry, latency metrics, background job monitoring, security alerts, or admin audit log viewer.
3. **Core Field Workflows (Phase 8 & Phase 9)**:
   - Android: Edit/delete permits, edit diary notes & delete diary entries, pre-save audio playback, remote media playback/photo viewing, full-screen photo lightbox, runtime `POST_NOTIFICATIONS` prompt, offline connectivity badge (`offline_badge`), logout confirmation when `pendingSyncCount > 0`, voluntary password change link, full Arabic (`values-ar`) & RTL strings.
   - Web: Audio playback (`audio_url`), inline diary note/summary editing & deletion, permit document upload via BFF/GCS, portfolio & timeline search/filtering/date navigation, forgot/reset password flow, active session management, organization & billing portal.
4. **AI Extraction Completeness (Phase 5)**: Missing structured extraction for written diary notes (`notes`), construction photographs, uploaded PDFs/documents, and permit documents (`PERMIT_DOC`).

---

## 5. Deployment & DevOps Problems (Phases 7, 14)

- `services/api/Dockerfile`: runs as `root`, uses unpinned `uv:latest`, hardcodes `--port 8000` (fails on Cloud Run `$PORT` / `8080` if unconfigured), lacks `HEALTHCHECK`.
- `apps/web/Dockerfile`: copies `public` and `assets` as root, lacks `--ignore-scripts`, lacks `HEALTHCHECK`.
- `DEPLOY.md`: copy-paste `gcloud run deploy` omits Cloud SQL Unix socket `DATABASE_URL` (`/cloudsql/...`), `--set-secrets` (`JWT_SECRET`, `MEDIA_URL_SIGNING_SECRET`), custom least-privilege service accounts, `--min-instances` / Cloud Tasks worker wiring, Cloud Scheduler alert job, `CORS_ORIGINS`, `PUBLIC_API_BASE_URL`, Cloud SQL automated backup/PITR/SSL, and Cloud Monitoring/Logging setup. No scripted deploy/backup/restore automation exists.
- `docker-compose.yml`: mounts `.env.example` directly (dev secrets), hardcodes `postgres:postgres`, exposes Postgres port `5432` directly, lacks service `healthcheck`s.
- `.github/workflows/ci.yml`: lacks least-privilege `permissions:`, mutable action tags instead of SHAs or controlled policy, missing secret scanning, dependency vulnerability auditing (`pip-audit`/`npm audit`), container build smoke checks, Android `lint`/release build verification, and separate `dev`/`staging`/`production` deployment workflows with approval gates.

---

## 6. Performance Bottlenecks

- Global Postgres advisory lock `pg_advisory_xact_lock(724242)` in `bump_sync_version()` serializes ALL sync writes, media completions, project edits, and AI status updates across every organization on one lock.
- `sync_push` performs up to 200 sequential `db.commit()` transactions with redundant `ProjectMember` lookups (~600 SQL roundtrips per batch).
- `get_engine()` (`db/session.py`) configures zero pool sizing (`pool_size`, `max_overflow`, `pool_recycle`) or Postgres `statement_timeout`.
- Unpaginated endpoints (`/v1/projects`, `/permits`, `/members`, `/days/{date}`) + `N+1` `storage.Client()` instantiations inside request loops + unbounded `Promise.all` photo compression in PDF generation.
- Room DAOs lack indices on `audio_upload_status`, `upload_status`, and `sync_dirty`; Postgres lacks indexes on several FK/lookup columns.

---

## 7. Database Risks (Phase 6)

- Room `DatabaseModule.kt:30` sets `.fallbackToDestructiveMigration(dropAllTables = true)` with zero `@ForeignKey` constraints—any schema bump silently destroys un-synced field diaries.
- Postgres `contracts/schema.sql` omits `ON DELETE` clauses on `projects.created_by`, `permits.created_by`, `site_logs.author_id`, and `refresh_tokens.replaced_by`, blocking user deletion/anonymization and cleanup.
- No automated backup script, restore script, or tested restoration procedure exists.

---

## 8. Mobile Application Summary (`apps/mobile/`)

- **Sync/Storage Criticals**: Audio upload overwrite (`SyncEngine.kt:566`), non-durable backfill (`L195,240-276`), silently dropped server rejections, `PROJECT_DELETED` missing on photos, non-2xx treated as infinite retry, missing `Mutex`, periodic sync surviving logout, `cacheDir/captures` leak, Room destructive migration fallback.
- **Security**: Global cleartext HTTP, plaintext `SharedPreferences` + `.apply()` rotation race, 401 refresh failure cross-user Room/file leak, unrequested `POST_NOTIFICATIONS`, pre-check logged-out notification render (`SiteDiaryFirebaseMessagingService.kt:53`), non-private lockscreen notifications.
- **Release Blockers**: No `signingConfigs` / release keystore instructions, `isMinifyEnabled = false`, incomplete 7-line `proguard-rules.pro`, `local.properties` overriding CI `API_BASE_URL`, generic Android launcher/notification icons, missing `google-services.json` docs, zero `values-ar` strings, missing UI features (edit/delete permits & logs, audio preview, photo lightbox, offline banner), insufficient unit/worker/VM tests.

---

## 9. Web Application Summary (`apps/web/`)

- **Security**: Missing security headers, missing CSRF/Origin guard, open redirect `/\evil.com` in `sanitizeNextPath`, unverified JWT redirect loop, broken transient-error handling in middleware/BFF, `must_change_password` bypass on `/api/*`, unconstrained BFF routes/sizes, `isSessionCookieSecure()` failing open, `NEXT_PUBLIC_DEMO_MODE` risk in prod builds.
- **Product/PDF/UX**: `isOwner` fail-open bug, stale extraction UI on retry, missing search/filter/date jump/edit/delete/audio player/permit upload, SaaS tenant/role/billing/audit/export absence, `wrap={false}` PDF overflow & missing Urdu/Arabic general text fonts, raw `<a href>` PDF errors, `Modal` a11y gaps, un-tested UI/React components & middleware.

---

## 10. Legal & Commercial Documentation Gaps (Phase 12)

Only proprietary `LICENSE` (29 lines) and `docs/site-diary-beginner-guide.pdf` exist. Missing: Privacy Policy, Terms of Service, Data Processing Agreement (DPA), Cookie Policy, Acceptable Use Policy, Installation Guide, Administrator Guide, User Guide, API Documentation, Backup & Recovery Guide, Troubleshooting Guide, Release Notes, and Commercial Licensing Documentation (explicitly protecting proprietary rights in `LICENSE`).

---

## Remediation Order
Execution proceeds immediately in source code across Phases 2–15:
1. **Phases 2, 3, 5, 6, 10, 11 (Backend, DB Migrations, Multi-Tenancy, Security, AI Queue, Audit Logs, Tests)**
2. **Phases 4 & 8 (Android Offline Sync Fixes, Security, UX/Features, Release Config & Tests)**
3. **Phases 9 & 10 UI (Web Security, Commercial SaaS Portal, PDF Fixes, Responsive UI & Tests)**
4. **Phases 7, 12, 13, 14, 15 (Cloud Run/Cloud SQL/Backup Scripts & Docs, Legal/Product Suite, CI/CD + Security Scans, Full Verification & `FINAL_COMMERCIAL_READINESS_REPORT.md`)**
