# 11 — GCP Deployment & Secret Manager Runbook

For complete deployment commands, see [`DEPLOY.md`](../DEPLOY.md) and [`infra/scripts/`](../infra/scripts/).

> **Verification Status:** Infrastructure scripts (`setup-gcp.sh`, `deploy-gcp.sh`, `backup-db.sh`, `restore-db.sh`, `verify-backup-restore.sh`) and Docker/CD definitions have been validated locally and via CI checks, while **live GCP staging/production deployment remains `BLOCKED BY EXTERNAL CREDENTIALS`** (requires an active GCP project, billing account, Secret Manager secrets, Vertex AI entitlement, and GitHub WIF configuration).

---

## Infrastructure Components

- **Cloud Run Services (`site-diary-api`, `site-diary-web`):** Non-root container images built from `services/api/Dockerfile` and `apps/web/Dockerfile` with explicit `/healthz` / `/readyz` and `/api/health` readiness checks.
- **Cloud SQL (`site-diary-pg`):** PostgreSQL 16 with automatic storage growth, daily physical backups, and 7-day point-in-time recovery (PITR).
- **Cloud Storage (`${PROJECT_ID}-site-diary-media`):** Private bucket with Uniform Bucket-Level Access, Public Access Prevention, versioning, and CORS rules for direct signed transfers.
- **Cloud Tasks (`site-diary-extraction`):** Durable extraction queue with retry backoff and OIDC + optional shared-secret authenticated delivery. In `infra/scripts/deploy-gcp.sh`, `CLOUD_TASKS_HANDLER_URL` is configured as the base `${API_URL}` (with no path suffix), because `app/services/extraction_worker.py` appends `/v1/internal/tasks/extraction` cleanly when enqueueing tasks and validates the base URL as the OIDC token audience.
- **Cloud Run Job (`site-diary-permit-alerts`):** Daily permit expiry alerting cron (`0 7 * * *` `Asia/Karachi`), wired with `STORAGE_BACKEND=gcs` and `GCS_BUCKET=${GCS_BUCKET}` so permit attachment state remains consistent across workers.
- **Cloud Run Job (`site-diary-media-cleanup`):** Scheduled media & orphan cleanup worker (`uv run python -m app.jobs.media_cleanup`) wired with `STORAGE_BACKEND=gcs` and `GCS_BUCKET=${GCS_BUCKET}`, cleaning expired reservations, expired upload tickets, incomplete uploads, aged unattached objects (preserving fresh within-grace uploads and valid customer attachments), and expired failed extraction jobs while writing auditable records to `media_cleanup_runs` and `audit_logs`.

---

## Secret Manager & External Configuration

`services/api/app/core/secrets.py` resolves secret payloads natively via GCP Application Default Credentials (`fetch_gcp_secret`):
- Explicit resource references (`sm://projects/<proj>/secrets/<name>/versions/latest` or `sm://<secret-id>`), or
- Implicit `GCP_SECRET_MANAGER_ENABLED=true` resolution for `site-diary-jwt-secret` and `site-diary-media-url-signing-secret`.

Cloud Run binds secrets securely as environment injections (`--set-secrets=...`) in [`infra/scripts/deploy-gcp.sh`](../infra/scripts/deploy-gcp.sh), ensuring secrets never live in source control or image layers.

### Required External Credentials & Optional Add-ons
- **Mandatory for staging/production boot (`validate_runtime_configuration`):** Cloud SQL connection & password secret, 32+ char `JWT_SECRET`, distinct 32+ char `MEDIA_URL_SIGNING_SECRET`, HTTPS `CORS_ORIGINS`, GCS bucket (`STORAGE_BACKEND=gcs`), and Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=true`, `GCP_PROJECT_ID`).
- **Mandatory for GitHub CD (`.github/workflows/cd.yml`):** `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_DEPLOY_SERVICE_ACCOUNT` configured on GitHub Environments (`staging`, `production`) with protected deployment reviewers on `production`.
- **Optional external integrations:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`, `FCM_PROJECT_ID`, `SMTP_*`, and `SCHEDULER_SHARED_SECRET`.
