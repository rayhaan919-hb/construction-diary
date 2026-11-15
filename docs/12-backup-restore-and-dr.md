# 12 — Backup, Restore & Disaster Recovery Runbook

---

## RPO / RTO Targets & Retention

- **Recovery Point Objective (RPO):** **<= 5 minutes** for PostgreSQL data when Cloud SQL Point-in-Time Recovery (PITR) binary logging is active (`--enable-point-in-time-recovery` + automated daily backup window); **24 hours** against daily physical snapshots alone.
- **Recovery Time Objective (RTO):** **< 30 minutes** using `infra/scripts/restore-db.sh` (managed Cloud SQL backup clone or logical `pg_restore` into a clean replacement instance + Cloud Run environment update / cutover).
- **Backup Retention:** Automated Cloud SQL daily physical snapshots retained for **14 days** (`7 days` transaction log history for PITR); logical `pg_dump` exports archived in `gs://${PROJECT_ID}-site-diary-backups/dumps/`.
- **Media Protection:** GCS Bucket Versioning enabled on `${PROJECT_ID}-site-diary-media` to recover site photos, voice notes, and permit PDFs against accidental overwrites or deletions.

---

## Operational Procedures

### 1. Creating an On-Demand Backup + GCS Dump
```bash
PROJECT_ID="your-gcp-project" ./infra/scripts/backup-db.sh
```
This script triggers both:
1. A managed Cloud SQL physical backup (`gcloud sql backups create`).
2. A logical compressed PostgreSQL archive written to `gs://${PROJECT_ID}-site-diary-backups/dumps/`.

### 2. Restoring to an Alternate Validation Instance
```bash
CONFIRM_RESTORE=yes \
PROJECT_ID="your-gcp-project" \
SOURCE_INSTANCE="site-diary-pg" \
TARGET_INSTANCE="site-diary-pg-restore" \
BACKUP_ID="<backup-id>" \
  ./infra/scripts/restore-db.sh
```
Without `CONFIRM_RESTORE=yes`, `restore-db.sh` defaults safely to dry-run mode.

### 3. Automated pg_dump / pg_restore + Media Integrity Drill
```bash
DATABASE_URL="postgresql://postgres:<PASSWORD>@127.0.0.1:5432/site_diary" \
LOCAL_STORAGE_DIR="/path/to/media" \
  ./infra/scripts/verify-backup-restore.sh
```
This non-destructive script executes six verification steps and drops the temporary verification database cleanly on exit:
1. Records source `alembic_version` and row counts (`organizations`, `users`, `projects`, `site_logs`, `site_log_photos`).
2. Exports a custom-format archive (`pg_dump --format=custom --no-owner --no-privileges`).
3. Creates an isolated temporary verification database (`site_diary_restore_verify_<ts>`).
4. Restores into the verification database with `pg_restore --exit-on-error`.
5. Fails non-zero on any schema revision or core row count mismatch.
6. When `LOCAL_STORAGE_DIR` or `MEDIA_DIR` is set, archives and extracts the media directory via compressed `tar` and verifies an identical file list and SHA-256 checksum manifest (`gsutil` / `gcloud storage rsync` should be verified separately when targeting GCS buckets in live GCP).

### Local Verification Evidence (2026-11-15)
Executed against PostgreSQL 16 (Alembic revision `0003_media_reservations`) seeded via real FastAPI routes (`POST /v1/organizations/register`, `POST /v1/projects`, `POST /v1/projects/{id}/permits`, `POST /v1/media/reservations`, `POST /v1/media/upload-url`, `PUT` photo upload, `POST /v1/sync/push`, `POST /v1/media/complete`):
- `verify-backup-restore.sh` passed (`rev=0003_media_reservations, orgs=1, users=1, projects=1, logs=1, photos=1`, `Media backup/restore verified (1 files, SHA-256 identical)`).
- Independent destructive restore simulation: dumped DB + tarred media, **dropped** the source database (`WITH (FORCE)`) and **deleted** the source media directory, restored into a clean Postgres database and fresh storage directory, booted a fresh FastAPI application against the restored DB + media, logged in, fetched the restored project (`Bridge Pier #9`), permit (`Piling Permit`), log (`DR drill rebar inspection`), and downloaded the signed photo with identical byte-for-byte SHA-256 (`98888c2bd07a4b0ec55f8f86998a0a44f88f3c304140702f6b1a2ad532d5f1a9`).
