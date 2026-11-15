# Security Policy

Construction Diary is commercial multi-tenant SaaS software for managing construction site logs, permits, voice/photo records, and regulatory compliance across distributed field teams. Security controls are enforced across backend, web BFF, Android mobile client, and cloud deployment layers.

---

## Supported Versions

| Component | Target | Security Status |
|---|---|---|
| Backend API (`services/api`) | FastAPI + PostgreSQL 16 + Alembic | Supported (`main` branch) |
| Web Portal (`apps/web`) | Next.js App Router + HttpOnly BFF | Supported (`main` branch) |
| Android Field App (`apps/mobile`) | Kotlin + Jetpack Compose + Room | Supported (`main` branch) |

---

## Implemented Security Controls

### 1. Authentication, Passwords & Sessions
- **Argon2id password hashing** (`argon2-cffi` via `services/api/app/services/auth.py`) with transparent rehash-on-login upgrades and dummy verification timing equalization against account enumeration.
- **Short-lived HMAC-SHA256 JWT access tokens** (`ACCESS_TOKEN_TTL_SECONDS=900`, explicit `iss`/`aud` claims) paired with opaque single-use refresh tokens.
- **Refresh-token rotation & reuse detection**: reusing a rotated refresh token revokes the entire token family/session chain.
- **Account lockout & per-endpoint rate limiting** on login (`LOGIN_RATE_LIMIT_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`), registration, and password resets.
- **Session management & global revocation**: changing password, triggering password reset, logout all, or org suspension revokes active refresh tokens.

### 2. Multi-Tenant & Role-Based Authorization
- Organization-scoped tenancy with plan seat/project/storage quota checks and suspension enforcement (`ensure_org_active` in `services/api/app/services/saas.py`).
- Explicit organization roles (`ORG_OWNER`, `ORG_ADMIN`, `PROJECT_MANAGER`, `SUPERVISOR`, `MEMBER`) and project roles (`OWNER`, `SUPERVISOR`, `VIEWER`) enforced server-side in route dependencies (`services/api/app/api/deps.py`, `services/api/app/core/permissions.py`).
- Cross-tenant and non-member access attempts fail with uniform HTTP 403/404 responses without leaking existence metadata.

### 3. Media Upload & Download Security
- Signed upload tickets (`UploadTicket` table) bound to the authenticated user, project, target record (`AUDIO`, `PHOTO`, `PERMIT_DOC`), expected byte bounds, and short expiry windows (`SIGNED_URL_TTL_SECONDS`).
- Immutable UUID-derived object keys sanitized against path traversal (`sanitize_relative_object_key` in `services/api/app/services/media_security.py`).
- Existing-object overwrite prevention and single-use ticket replay prevention on `/v1/media/complete`.
- Magic-byte signature inspection (JPEG, PNG, WebP, PDF, AAC/M4A/MP3/WAV) rejecting executables, scripts, and disguised content types.
- Local storage signed GET verification plus SSRF-hardened web server-side PDF photo fetcher (`apps/web/src/lib/pdf/photo-fetcher.ts`) blocking private/loopback/CGNAT/link-local metadata IPs and private DNS resolution.

### 4. Web Portal & BFF Hardening
- Backend JWT tokens stored strictly inside signed HttpOnly cookies; zero bearer tokens exposed in browser JS / `localStorage`.
- CSRF origin/referer and `Sec-Fetch-Site` enforcement on `/api/auth/*` and state-changing `/api/bff/*` requests (`apps/web/src/lib/csrf.ts`).
- Strict security headers in `apps/web/next.config.ts` (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, Content-Security-Policy).

### 5. Android Client Security
- `AppPreferences` encrypts stored access tokens, refresh tokens, serialized user profiles, and FCM tokens using `AES/GCM/NoPadding` backed by Android Keystore (`SessionCrypto` in `apps/mobile/app/src/main/java/com/sitediary/mobile/data/prefs/AppPreferences.kt`).
- `clearAllSettingsOnLogout()` clears both DataStore settings and `authPrefs` encrypted session/FCM state while preserving the user's selected locale.
- Release builds enforce `android:usesCleartextTraffic="false"`, disable backups (`android:allowBackup="false"`), restrict debug network rules to local emulators (`network_security_config.xml`), and enable R8 shrinking/obfuscation (`minifyEnabled = true`).

### 6. Production Secrets Fail-Closed Policy
- `validate_runtime_configuration()` (`services/api/app/core/config.py`) validates secrets, origin rules, seed disabling, TLS URLs, and GCS configuration at startup when `ENV=staging|production`, failing closed on weak defaults.
- Direct Google Secret Manager resolution (`sm://` URIs and `GCP_SECRET_MANAGER_ENABLED=true`) via `services/api/app/core/secrets.py`.

---

## Reporting a Vulnerability

Please **do not** open public GitHub issues for suspected security vulnerabilities.
Report security findings privately to the repository maintainer (`rayhaan919@gmail.com`) with:
1. Affected component (`services/api`, `apps/web`, `apps/mobile`, or `infra/`) and commit SHA.
2. Reproduction steps or proof-of-concept request/payload.
3. Expected vs. observed impact and any suggested remediation.

Confirmed critical/high vulnerabilities are triaged promptly, patched on a private branch, and covered by automated regression tests before disclosure.
