# 12 — Backup, Restore & Disaster Recovery Runbook

---

## RPO / RTO Targets

- **Cloud SQL PITR Enabled:** Point-in-time recovery via transaction logs (target RPO <= 5 minutes; automated daily snapshots retained for 14 days).
- **GCS Bucket Versioning Enabled:** Protects uploaded site photos, voice notes, and permit PDFs against accidental overwrites or deletions.

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

### 3. Automated pg_dump / pg_restore Integrity Drill
```bash
DATABASE_URL="postgresql://postgres:<PASSWORD>@127.0.0.1:5432/site_diary" \
  ./infra/scripts/verify-backup-restore.sh
```
This non-destructive script dumps the live database, restores it into an isolated ephemeral database, verifies matching Alembic schema revision (`alembic_version`) and core row counts (`organizations`, `users`, `projects`, `site_logs`), and drops the temporary verification database cleanly on exit.
