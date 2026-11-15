# 11 — GCP Deployment & Secret Manager Runbook

For complete deployment commands, see [`DEPLOY.md`](../DEPLOY.md) and [`infra/scripts/`](../infra/scripts/).

---

## Infrastructure Components

- **Cloud Run (`site-diary-api`, `site-diary-web`):** Non-root container images built from `services/api/Dockerfile` and `apps/web/Dockerfile` with explicit `/healthz` / `/readyz` and `/api/health` readiness checks.
- **Cloud SQL (`site-diary-pg`):** PostgreSQL 16 with automatic storage growth, daily physical backups, and 7-day point-in-time recovery (PITR).
- **Cloud Storage (`${PROJECT_ID}-site-diary-media`):** Private bucket with Uniform Bucket-Level Access, Public Access Prevention, versioning, and CORS rules for direct signed transfers.
- **Cloud Tasks (`site-diary-extraction`):** Durable extraction queue with retry backoff and OIDC + shared-secret authenticated delivery to `/internal/tasks/extract`.
- **Cloud Scheduler + Cloud Run Job (`site-diary-permit-alerts`):** Daily permit expiry alerting cron (`0 7 * * *` `Asia/Karachi`).

---

## Secret Manager Integration

`services/api/app/core/secrets.py` resolves secret payloads natively via GCP Application Default Credentials (`fetch_gcp_secret`):
- Explicit resource references (`sm://projects/<proj>/secrets/<name>/versions/latest` or `sm://<secret-id>`), or
- Implicit `GCP_SECRET_MANAGER_ENABLED=true` resolution for `site-diary-jwt-secret` and `site-diary-media-url-signing-secret`.

Cloud Run binds secrets securely as environment injections (`--set-secrets=...`) in [`infra/scripts/deploy-gcp.sh`](../infra/scripts/deploy-gcp.sh), ensuring secrets never live in source control or image layers.
