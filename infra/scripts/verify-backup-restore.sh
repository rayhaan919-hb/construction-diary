#!/usr/bin/env bash
set -euo pipefail

# Local / CI backup & restore verification drill using pg_dump + pg_restore
# (or psql on plain dumps) against a temporary PostgreSQL database.
# Fails non-zero if restored row counts, schema revision, or constraints break.

DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to the source PostgreSQL connection string}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

DUMP_FILE="${WORK_DIR}/site_diary_backup.dump"
VERIFY_DB="site_diary_restore_verify_$(date +%s)"

echo "==> [1/5] Recording source alembic revision and core table counts..."
SRC_REV="$(psql "${DATABASE_URL}" -tAc "SELECT version_num FROM alembic_version LIMIT 1;")"
SRC_ORGS="$(psql "${DATABASE_URL}" -tAc "SELECT count(*) FROM organizations;")"
SRC_USERS="$(psql "${DATABASE_URL}" -tAc "SELECT count(*) FROM users;")"
SRC_PROJECTS="$(psql "${DATABASE_URL}" -tAc "SELECT count(*) FROM projects;")"
SRC_LOGS="$(psql "${DATABASE_URL}" -tAc "SELECT count(*) FROM site_logs;")"

echo "==> [2/5] Creating pg_dump custom-format archive..."
pg_dump --format=custom --no-owner --no-privileges --file="${DUMP_FILE}" "${DATABASE_URL}"
test -s "${DUMP_FILE}"

ADMIN_URL="${DATABASE_URL%/*}/postgres"
VERIFY_URL="${DATABASE_URL%/*}/${VERIFY_DB}"

cleanup_verify_db() {
  psql "${ADMIN_URL}" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"${VERIFY_DB}\";" >/dev/null 2>&1 || true
}
trap 'cleanup_verify_db; rm -rf "${WORK_DIR}"' EXIT

echo "==> [3/5] Creating clean target verification database '${VERIFY_DB}'..."
psql "${ADMIN_URL}" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${VERIFY_DB}\";"

echo "==> [4/5] Restoring archive into '${VERIFY_DB}'..."
pg_restore --no-owner --no-privileges --exit-on-error --dbname="${VERIFY_URL}" "${DUMP_FILE}"

echo "==> [5/5] Verifying schema revision and table counts match source..."
DST_REV="$(psql "${VERIFY_URL}" -tAc "SELECT version_num FROM alembic_version LIMIT 1;")"
DST_ORGS="$(psql "${VERIFY_URL}" -tAc "SELECT count(*) FROM organizations;")"
DST_USERS="$(psql "${VERIFY_URL}" -tAc "SELECT count(*) FROM users;")"
DST_PROJECTS="$(psql "${VERIFY_URL}" -tAc "SELECT count(*) FROM projects;")"
DST_LOGS="$(psql "${VERIFY_URL}" -tAc "SELECT count(*) FROM site_logs;")"

if [[ "${SRC_REV}" != "${DST_REV}" || "${SRC_ORGS}" != "${DST_ORGS}" || \
      "${SRC_USERS}" != "${DST_USERS}" || "${SRC_PROJECTS}" != "${DST_PROJECTS}" || \
      "${SRC_LOGS}" != "${DST_LOGS}" ]]; then
  echo "VERIFICATION FAILED: mismatch between source and restored DB" >&2
  echo "Source:  rev=${SRC_REV} orgs=${SRC_ORGS} users=${SRC_USERS} projects=${SRC_PROJECTS} logs=${SRC_LOGS}" >&2
  echo "Restore: rev=${DST_REV} orgs=${DST_ORGS} users=${DST_USERS} projects=${DST_PROJECTS} logs=${DST_LOGS}" >&2
  exit 1
fi

echo "Backup & restore verification PASSED (rev=${DST_REV}, orgs=${DST_ORGS}, users=${DST_USERS}, projects=${DST_PROJECTS}, logs=${DST_LOGS})."
