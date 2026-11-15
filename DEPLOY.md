# Deployment Runbook (Docker, GCP Cloud Run, Cloud SQL, GCS & CI/CD)

Follow this runbook to run Construction Diary locally via Docker Compose or deploy the hardened production stack to Google Cloud Platform.

---

## 1. Automated GCP Scripts (`infra/scripts/`)

The repository includes parameterized deployment and disaster-recovery scripts under `infra/scripts/`:

- [`infra/scripts/setup-gcp.sh`](infra/scripts/setup-gcp.sh) — Enables required GCP APIs, creates Artifact Registry, provisions least-privilege service accounts, creates Cloud SQL PostgreSQL 16 (with PITR and automated backups), creates private GCS media/backup buckets with versioning & CORS, creates Secret Manager entries, and creates the Cloud Tasks extraction queue.
- [`infra/scripts/deploy-gcp.sh`](infra/scripts/deploy-gcp.sh) — Builds and pushes container images for `services/api` and `apps/web`, runs `alembic upgrade head` via a Cloud Run Job, deploys Cloud Run services with Secret Manager mounts, updates `site-diary-permit-alerts` and `site-diary-media-cleanup` Cloud Run Jobs (with `STORAGE_BACKEND=gcs`), and runs `/readyz` + `/api/health` readiness smoke checks.
- [`infra/scripts/backup-db.sh`](infra/scripts/backup-db.sh) — Triggers an on-demand Cloud SQL physical backup plus an exported compressed SQL snapshot in `gs://${PROJECT_ID}-site-diary-backups`.
- [`infra/scripts/restore-db.sh`](infra/scripts/restore-db.sh) — Restores a Cloud SQL backup or SQL snapshot onto a target instance (dry-run by default; requires `CONFIRM_RESTORE=yes`).
- [`infra/scripts/verify-backup-restore.sh`](infra/scripts/verify-backup-restore.sh) — Runs a non-destructive local/CI `pg_dump` + `pg_restore` verification into an ephemeral database, asserts Alembic revision and core row counts match, and verifies compressed media archive SHA-256 parity when `LOCAL_STORAGE_DIR` / `MEDIA_DIR` is set.

```bash
export PROJECT_ID="your-gcp-project"
export REGION="us-central1"

chmod +x infra/scripts/*.sh
./infra/scripts/setup-gcp.sh
# Populate database URL in Secret Manager:
echo -n "postgresql://appuser:<STRONG_PASSWORD>@/site_diary?host=/cloudsql/${PROJECT_ID}:${REGION}:site-diary-pg" \
  | gcloud secrets versions add site-diary-database-url --data-file=- --project="${PROJECT_ID}"

./infra/scripts/deploy-gcp.sh
```

---

## 2. Production Secrets & Configuration Fail-Closed Policy

When `ENV=staging` or `ENV=production`, the FastAPI backend calls `validate_runtime_configuration()` at startup and **refuses to boot** if any of the following are missing or insecure:
- `JWT_SECRET` and `MEDIA_URL_SIGNING_SECRET` must each be >= 32 characters, distinct from each other, and free of known placeholder strings.
- `ENABLE_DEV_SEED` must be `false` and `SEED_*_PASSWORD` variables must remain unset.
- `CORS_ORIGINS` must list explicit `https://` origins (wildcard `*` is rejected).
- In `ENV=production`, `USE_MOCK_GEMINI=false`, `STORAGE_BACKEND=gcs`, non-empty `GCS_BUCKET`, HTTPS `PUBLIC_API_BASE_URL`, and non-default `DATABASE_URL` credentials are mandatory.

Values prefixed with `sm://` or resolved via `GCP_SECRET_MANAGER_ENABLED=true` are automatically fetched from Google Secret Manager using Application Default Credentials (`services/api/app/core/secrets.py`).

---

## 3. GitHub Actions CI/CD & Workload Identity Federation (WIF)

- **Continuous Integration** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): Runs Gitleaks secret scanning, deployment script syntax checks (`bash -n`), `apps/web` (`npm audit --omit=dev --audit-level=high`, `typecheck`, `lint`, `test`, `build`), `services/api` (`pip-audit`, `ruff check`, `mypy`, `pytest -q`), and `apps/mobile` (`./gradlew testDebugUnitTest lintDebug`, fail-closed `bundleRelease` check, and signed APK/AAB verification — see [`docs/15-android-release-signing.md`](docs/15-android-release-signing.md)).
- **Continuous Delivery** ([`.github/workflows/cd.yml`](.github/workflows/cd.yml)): Triggered on `v*` tags or manual `workflow_dispatch` into `staging` / `production`. Builds container images for API and Web, and when `deploy_services=true` is selected, authenticates via keyless Workload Identity Federation and invokes `./infra/scripts/deploy-gcp.sh`.

Configure the following GitHub Environment variables per target environment (`staging`, `production`):
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

---

## 4. Cloud SQL & Backup / Restore Verification Drill

Automated daily backups + 7-day point-in-time recovery (PITR) are enabled by `setup-gcp.sh`. Perform quarterly restore drills:

```bash
# Cloud SQL restore into a staging validation instance
CONFIRM_RESTORE=yes TARGET_INSTANCE=site-diary-pg-restore BACKUP_ID=<id> \
  PROJECT_ID="${PROJECT_ID}" ./infra/scripts/restore-db.sh

# Local / CI logical backup-restore integrity verification
DATABASE_URL="postgresql://postgres:<PASSWORD>@127.0.0.1:5432/site_diary" \
  ./infra/scripts/verify-backup-restore.sh
```

---

## 5. Daily Permit Expiry Scheduler (Cloud Run Job + Cloud Scheduler)

Schedule the `site-diary-permit-alerts` Cloud Run Job daily at 07:00 `Asia/Karachi`:

```bash
gcloud scheduler jobs create http permit-alerts-daily \
  --location="${REGION}" \
  --schedule="0 7 * * *" \
  --time-zone="Asia/Karachi" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/site-diary-permit-alerts:run" \
  --http-method=POST \
  --oauth-service-account-email="site-diary-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${PROJECT_ID}"
```

---

## 6. Local Docker Compose Deployment

```bash
cp .env.example .env
# Edit .env and supply strong secrets / Postgres credentials
docker compose up --build -d
```

- PostgreSQL binds exclusively to `127.0.0.1:5432`
- FastAPI API exposes `/healthz` and `/readyz` on `127.0.0.1:8000`
- Next.js Web BFF exposes `/api/health` on `127.0.0.1:3000` (with Web only starting once API passes `/readyz`)

---

## 7. Mobile (`apps/mobile`) & Firebase FCM Setup

1. Place Firebase `google-services.json` in `apps/mobile/app/google-services.json` to enable FCM push alerts (`apps/mobile/app/build.gradle.kts` conditionally applies `com.google.gms.google-services` only when that file exists). If `google-services.json` is omitted (e.g., local evaluation or CI builds), the app compiles and runs cleanly while `FcmTokenManager` logs a warning and skips FCM registration.
2. Provide the backend FCM project ID (`FCM_PROJECT_ID`) and service account credentials (`GOOGLE_APPLICATION_CREDENTIALS` or attached runtime SA) when `NOTIFIER=fcm` is enabled in production.
3. Configure `PROD_API_BASE_URL` (HTTPS Cloud Run API URL) and external keystore secrets (`ANDROID_KEYSTORE_PATH` / `ANDROID_KEYSTORE_BASE64`, passwords, alias) for Android production release builds (`targetSdk = 36`, `compileSdk = 37`); missing production config fails the Gradle build closed (cleartext HTTP is disabled in Android release network security config). See [`docs/15-android-release-signing.md`](docs/15-android-release-signing.md).
