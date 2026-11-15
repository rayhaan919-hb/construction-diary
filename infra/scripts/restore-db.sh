#!/usr/bin/env bash
set -euo pipefail

# Restore a Cloud SQL backup onto a target Cloud SQL instance.
# Defaults to dry-run output unless CONFIRM_RESTORE=yes is explicitly passed.

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your target GCP project ID}"
TARGET_INSTANCE="${TARGET_INSTANCE:-site-diary-pg-restore}"
SOURCE_INSTANCE="${SOURCE_INSTANCE:-site-diary-pg}"
BACKUP_ID="${BACKUP_ID:-}"
SQL_DUMP_URI="${SQL_DUMP_URI:-}"
DB_NAME="${DB_NAME:-site_diary}"
CONFIRM_RESTORE="${CONFIRM_RESTORE:-no}"

if [[ -z "${BACKUP_ID}" && -z "${SQL_DUMP_URI}" ]]; then
  echo "ERROR: Provide either BACKUP_ID (Cloud SQL backup ID) or SQL_DUMP_URI (gs://...sql.gz)." >&2
  exit 1
fi

if [[ "${CONFIRM_RESTORE}" != "yes" ]]; then
  echo "DRY RUN ONLY (set CONFIRM_RESTORE=yes to execute)."
  if [[ -n "${BACKUP_ID}" ]]; then
    echo "Would restore backup '${BACKUP_ID}' from '${SOURCE_INSTANCE}' -> '${TARGET_INSTANCE}'."
  else
    echo "Would import '${SQL_DUMP_URI}' into database '${DB_NAME}' on '${TARGET_INSTANCE}'."
  fi
  exit 0
fi

if [[ -n "${BACKUP_ID}" ]]; then
  echo "==> Restoring Cloud SQL backup ${BACKUP_ID} from ${SOURCE_INSTANCE} onto ${TARGET_INSTANCE}..."
  gcloud sql backups restore "${BACKUP_ID}" \
    --restore-instance="${TARGET_INSTANCE}" \
    --backup-instance="${SOURCE_INSTANCE}" \
    --project="${PROJECT_ID}" \
    --quiet
else
  echo "==> Importing SQL archive ${SQL_DUMP_URI} into ${TARGET_INSTANCE}/${DB_NAME}..."
  gcloud sql import sql "${TARGET_INSTANCE}" "${SQL_DUMP_URI}" \
    --database="${DB_NAME}" \
    --project="${PROJECT_ID}" \
    --quiet
fi

echo "Restore completed on instance '${TARGET_INSTANCE}'."
