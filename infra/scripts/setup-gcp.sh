#!/usr/bin/env bash
set -euo pipefail

# Provision foundational Google Cloud infrastructure for Construction Diary:
# - Required APIs (Cloud Run, Cloud SQL, GCS, Secret Manager, Artifact Registry,
#   Cloud Tasks, Cloud Scheduler, Vertex AI, IAM)
# - Artifact Registry Docker repository
# - Service accounts & Workload Identity / least-privilege IAM roles
# - Cloud SQL PostgreSQL 16 instance & database (with automated backups + PITR)
# - GCS media bucket with uniform bucket-level access, versioning & CORS
# - Secret Manager secret shells (values generated or populated cleanly)
# - Cloud Tasks queue for durable AI extraction & Cloud Scheduler permit alert job

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your target GCP project ID}"
REGION="${REGION:-us-central1}"
AR_REPO="${AR_REPO:-site-diary}"
DB_INSTANCE="${DB_INSTANCE:-site-diary-pg}"
DB_NAME="${DB_NAME:-site_diary}"
DB_TIER="${DB_TIER:-db-custom-1-3840}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-site-diary-media}"
TASKS_QUEUE="${TASKS_QUEUE:-site-diary-extraction}"
API_SA_NAME="${API_SA_NAME:-site-diary-api-sa}"
WEB_SA_NAME="${WEB_SA_NAME:-site-diary-web-sa}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-site-diary-scheduler-sa}"
BACKUP_BUCKET="${BACKUP_BUCKET:-${PROJECT_ID}-site-diary-backups}"

API_SA_EMAIL="${API_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WEB_SA_EMAIL="${WEB_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA_EMAIL="${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> [1/7] Enabling GCP APIs in project ${PROJECT_ID}..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudtasks.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  --project="${PROJECT_ID}"

echo "==> [2/7] Creating Artifact Registry repository '${AR_REPO}'..."
if ! gcloud artifacts repositories describe "${AR_REPO}" \
  --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Construction Diary container images" \
    --project="${PROJECT_ID}"
fi

echo "==> [3/7] Creating dedicated least-privilege service accounts..."
for sa in "${API_SA_NAME}" "${WEB_SA_NAME}" "${SCHEDULER_SA_NAME}"; do
  if ! gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${sa}" \
      --display-name="${sa}" \
      --project="${PROJECT_ID}"
  fi
done

for role in \
  roles/cloudsql.client \
  roles/aiplatform.user \
  roles/cloudtasks.enqueuer \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${API_SA_EMAIL}" \
    --role="${role}" >/dev/null
done

# Required for Cloud Run V4 signed URL generation without local JSON key files.
gcloud iam service-accounts add-iam-policy-binding "${API_SA_EMAIL}" \
  --member="serviceAccount:${API_SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="${PROJECT_ID}" >/dev/null

echo "==> [4/7] Provisioning Cloud SQL PostgreSQL 16 (${DB_INSTANCE})..."
if ! gcloud sql instances describe "${DB_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud sql instances create "${DB_INSTANCE}" \
    --database-version=POSTGRES_16 \
    --tier="${DB_TIER}" \
    --region="${REGION}" \
    --storage-auto-increase \
    --backup-start-time="02:00" \
    --enable-point-in-time-recovery \
    --retained-backups-count=14 \
    --project="${PROJECT_ID}"
fi

if ! gcloud sql databases describe "${DB_NAME}" \
  --instance="${DB_INSTANCE}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud sql databases create "${DB_NAME}" \
    --instance="${DB_INSTANCE}" \
    --project="${PROJECT_ID}"
fi

echo "==> [5/7] Provisioning GCS media & backup buckets..."
for bucket in "${GCS_BUCKET}" "${BACKUP_BUCKET}"; do
  if ! gcloud storage buckets describe "gs://${bucket}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${bucket}" \
      --location="${REGION}" \
      --uniform-bucket-level-access \
      --public-access-prevention \
      --project="${PROJECT_ID}"
    gcloud storage buckets update "gs://${bucket}" --versioning
  fi
done

gcloud storage buckets add-iam-policy-binding "gs://${GCS_BUCKET}" \
  --member="serviceAccount:${API_SA_EMAIL}" \
  --role="roles/storage.objectAdmin" >/dev/null

CORS_FILE="$(mktemp)"
cat > "${CORS_FILE}" <<'EOF'
[
  {
    "origin": ["https://*"],
    "method": ["GET", "PUT", "HEAD"],
    "responseHeader": ["Content-Type", "x-goog-meta-upload-ticket"],
    "maxAgeSeconds": 3600
  }
]
EOF
gcloud storage buckets update "gs://${GCS_BUCKET}" --cors-file="${CORS_FILE}"
rm -f "${CORS_FILE}"

echo "==> [6/7] Ensuring Secret Manager entries exist..."
ensure_random_secret() {
  local name="$1"
  if ! gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud secrets create "${name}" --replication-policy="automatic" --project="${PROJECT_ID}"
    openssl rand -base64 48 | tr -d '\n' | gcloud secrets versions add "${name}" \
      --data-file=- --project="${PROJECT_ID}" >/dev/null
    echo "   Created secret ${name} with generated 48-byte random value."
  fi
}

ensure_placeholder_secret() {
  local name="$1"
  if ! gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud secrets create "${name}" --replication-policy="automatic" --project="${PROJECT_ID}"
    echo "   Created empty secret shell '${name}' (populate a version before production deploy)."
  fi
}

ensure_random_secret "site-diary-jwt-secret"
ensure_random_secret "site-diary-media-url-signing-secret"
ensure_random_secret "site-diary-cloud-tasks-shared-secret"
ensure_random_secret "site-diary-scheduler-shared-secret"
ensure_placeholder_secret "site-diary-database-url"
ensure_placeholder_secret "site-diary-stripe-secret-key"
ensure_placeholder_secret "site-diary-stripe-webhook-secret"
ensure_placeholder_secret "site-diary-smtp-password"

echo "==> [7/7] Creating Cloud Tasks extraction queue '${TASKS_QUEUE}'..."
if ! gcloud tasks queues describe "${TASKS_QUEUE}" \
  --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud tasks queues create "${TASKS_QUEUE}" \
    --location="${REGION}" \
    --max-attempts=5 \
    --min-backoff=10s \
    --max-backoff=300s \
    --max-dispatches-per-second=5 \
    --max-concurrent-dispatches=10 \
    --project="${PROJECT_ID}"
fi

echo "Setup complete."
echo "Next steps:"
echo "  1. Populate Secret Manager version 1 for 'site-diary-database-url' (e.g. postgresql://user:pass@/site_diary?host=/cloudsql/${PROJECT_ID}:${REGION}:${DB_INSTANCE})."
echo "  2. Run ./infra/scripts/deploy-gcp.sh with PROJECT_ID=${PROJECT_ID} REGION=${REGION}."
