#!/usr/bin/env bash
set -euo pipefail

# Trigger a consistent PostgreSQL backup in Cloud SQL and optionally export a
# portable custom-format pg_dump snapshot to the private backup GCS bucket.

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your target GCP project ID}"
DB_INSTANCE="${DB_INSTANCE:-site-diary-pg}"
DB_NAME="${DB_NAME:-site_diary}"
BACKUP_BUCKET="${BACKUP_BUCKET:-${PROJECT_ID}-site-diary-backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

echo "==> [1/2] Creating on-demand Cloud SQL physical backup on ${DB_INSTANCE}..."
gcloud sql backups create \
  --instance="${DB_INSTANCE}" \
  --description="manual-backup-${TIMESTAMP}" \
  --project="${PROJECT_ID}"

echo "==> [2/2] Exporting logical PostgreSQL SQL dump to gs://${BACKUP_BUCKET}..."
EXPORT_URI="gs://${BACKUP_BUCKET}/dumps/${DB_NAME}-${TIMESTAMP}.sql.gz"
gcloud sql export sql "${DB_INSTANCE}" "${EXPORT_URI}" \
  --database="${DB_NAME}" \
  --offload \
  --project="${PROJECT_ID}"

echo "Backup complete:"
echo "  GCS SQL archive: ${EXPORT_URI}"
echo "List recent backups with:"
echo "  gcloud sql backups list --instance=${DB_INSTANCE} --project=${PROJECT_ID}"
