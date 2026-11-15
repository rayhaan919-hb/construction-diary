#!/usr/bin/env bash
set -euo pipefail

# Local / CI backup & restore verification drill using pg_dump + pg_restore
# against a temporary PostgreSQL database (plus media asset archive check).
# Fails non-zero if restored row counts, schema revision, or constraints break.

DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL to the source PostgreSQL connection string}"
WORK_DIR="$(mktemp -d)"
VERIFY_DB="site_diary_restore_verify_$(date +%s)"
ADMIN_URL=""

cleanup_verify_db() {
  if [[ -n "${ADMIN_URL}" ]]; then
    psql -v ON_ERROR_STOP=1 -d "${ADMIN_URL}" -c "DROP DATABASE IF EXISTS \"${VERIFY_DB}\";" >/dev/null 2>&1 </dev/null || true
  fi
}
trap 'cleanup_verify_db; rm -rf "${WORK_DIR}"' EXIT

PYTHON_BIN=""
for candidate in python3 python; do
  if command -v "${candidate}" >/dev/null 2>&1 && "${candidate}" -c "import urllib.parse" >/dev/null 2>&1; then
    PYTHON_BIN="${candidate}"
    break
  fi
done

if [[ -n "${PYTHON_BIN}" ]]; then
  eval "$("${PYTHON_BIN}" - "${DATABASE_URL}" "${VERIFY_DB}" <<'PY'
import shlex, sys
from urllib.parse import urlsplit, urlunsplit

raw_url, verify_db = sys.argv[1], sys.argv[2]
parts = urlsplit(raw_url)
scheme = "postgresql" if parts.scheme.startswith("postgresql") else parts.scheme

def make_url(db_name: str) -> str:
    return urlunsplit((scheme, parts.netloc, f"/{db_name}", parts.query, ""))

src_url = urlunsplit((scheme, parts.netloc, parts.path or "/postgres", parts.query, ""))
admin_url = make_url("postgres")
verify_url = make_url(verify_db)
print(f"SRC_LIBPQ_URL={shlex.quote(src_url)}")
print(f"ADMIN_URL={shlex.quote(admin_url)}")
print(f"VERIFY_URL={shlex.quote(verify_url)}")
PY
)"
else
  SRC_LIBPQ_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
  ADMIN_URL="${SRC_LIBPQ_URL%\?*}"
  ADMIN_URL="${ADMIN_URL%/*}/postgres"
  VERIFY_URL="${SRC_LIBPQ_URL%\?*}"
  VERIFY_URL="${VERIFY_URL%/*}/${VERIFY_DB}"
fi

DUMP_FILE="site_diary_backup.dump"

query_scalar() {
  local db_url="$1"
  local sql="$2"
  psql -v ON_ERROR_STOP=1 -tAc "${sql}" -d "${db_url}" </dev/null | tr -d '[:space:]'
}

echo "==> [1/6] Recording source alembic revision and core table counts..."
SRC_REV="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT version_num FROM alembic_version LIMIT 1;")"
SRC_ORGS="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT count(*) FROM organizations;")"
SRC_USERS="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT count(*) FROM users;")"
SRC_PROJECTS="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT count(*) FROM projects;")"
SRC_LOGS="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT count(*) FROM site_logs;")"
SRC_PHOTOS="$(query_scalar "${SRC_LIBPQ_URL}" "SELECT count(*) FROM site_log_photos;")"

echo "==> [2/6] Creating pg_dump custom-format archive..."
(
  cd "${WORK_DIR}"
  pg_dump --format=custom --no-owner --no-privileges --file="${DUMP_FILE}" "${SRC_LIBPQ_URL}" </dev/null
  test -s "${DUMP_FILE}"
)

echo "==> [3/6] Creating clean target verification database '${VERIFY_DB}'..."
psql -v ON_ERROR_STOP=1 -d "${ADMIN_URL}" -c "CREATE DATABASE \"${VERIFY_DB}\";" </dev/null

echo "==> [4/6] Restoring archive into '${VERIFY_DB}'..."
(
  cd "${WORK_DIR}"
  pg_restore --no-owner --no-privileges --exit-on-error --dbname="${VERIFY_URL}" "${DUMP_FILE}" </dev/null
)

echo "==> [5/6] Verifying schema revision and table counts match source..."
DST_REV="$(query_scalar "${VERIFY_URL}" "SELECT version_num FROM alembic_version LIMIT 1;")"
DST_ORGS="$(query_scalar "${VERIFY_URL}" "SELECT count(*) FROM organizations;")"
DST_USERS="$(query_scalar "${VERIFY_URL}" "SELECT count(*) FROM users;")"
DST_PROJECTS="$(query_scalar "${VERIFY_URL}" "SELECT count(*) FROM projects;")"
DST_LOGS="$(query_scalar "${VERIFY_URL}" "SELECT count(*) FROM site_logs;")"
DST_PHOTOS="$(query_scalar "${VERIFY_URL}" "SELECT count(*) FROM site_log_photos;")"

if [[ "${SRC_REV}" != "${DST_REV}" || "${SRC_ORGS}" != "${DST_ORGS}" || \
      "${SRC_USERS}" != "${DST_USERS}" || "${SRC_PROJECTS}" != "${DST_PROJECTS}" || \
      "${SRC_LOGS}" != "${DST_LOGS}" || "${SRC_PHOTOS}" != "${DST_PHOTOS}" ]]; then
  echo "VERIFICATION FAILED: mismatch between source and restored DB" >&2
  echo "Source:  rev=${SRC_REV} orgs=${SRC_ORGS} users=${SRC_USERS} projects=${SRC_PROJECTS} logs=${SRC_LOGS} photos=${SRC_PHOTOS}" >&2
  echo "Restore: rev=${DST_REV} orgs=${DST_ORGS} users=${DST_USERS} projects=${DST_PROJECTS} logs=${DST_LOGS} photos=${DST_PHOTOS}" >&2
  exit 1
fi

echo "==> [6/6] Verifying media asset backup & restore integrity (if LOCAL_STORAGE_DIR / MEDIA_DIR set)..."
MEDIA_SRC="${MEDIA_DIR:-${LOCAL_STORAGE_DIR:-}}"
if [[ -n "${MEDIA_SRC}" && -d "${MEDIA_SRC}" ]]; then
  TAR_BIN="$(command -v /usr/bin/tar || command -v tar)"
  (
    cd "${WORK_DIR}"
    mkdir -p media-restore
    (cd "${MEDIA_SRC}" && "${TAR_BIN}" -czf - .) > media-backup.tar.gz
    "${TAR_BIN}" -xzf - -C media-restore < media-backup.tar.gz
  )
  MEDIA_RESTORE="${WORK_DIR}/media-restore"
  SRC_MANIFEST="$(cd "${MEDIA_SRC}" && find . -type f | LC_ALL=C sort | xargs -r sha256sum || true)"
  DST_MANIFEST="$(cd "${MEDIA_RESTORE}" && find . -type f | LC_ALL=C sort | xargs -r sha256sum || true)"
  if [[ "${SRC_MANIFEST}" != "${DST_MANIFEST}" ]]; then
    echo "Media archive checksum mismatch after restore!" >&2
    exit 1
  fi
  FILE_COUNT="$(printf '%s\n' "${SRC_MANIFEST}" | grep -c . || true)"
  echo "Media backup/restore verified (${FILE_COUNT} files, SHA-256 identical)."
else
  echo "MEDIA_DIR / LOCAL_STORAGE_DIR not set; DB-only verification completed (use gsutil/gcloud storage rsync for GCS buckets)."
fi

echo "Backup/restore verification PASSED: rev=${DST_REV}, orgs=${DST_ORGS}, users=${DST_USERS}, projects=${DST_PROJECTS}, logs=${DST_LOGS}, photos=${DST_PHOTOS}"
