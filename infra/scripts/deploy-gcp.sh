#!/usr/bin/env bash
set -euo pipefail

# Build, migrate, deploy, and smoke-check Construction Diary API + Web on Cloud Run.

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your target GCP project ID}"
REGION="${REGION:-us-central1}"
AR_REPO="${AR_REPO:-site-diary}"
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"

DB_INSTANCE="${DB_INSTANCE:-site-diary-pg}"
GCS_BUCKET="${GCS_BUCKET:-${PROJECT_ID}-site-diary-media}"
TASKS_QUEUE="${TASKS_QUEUE:-site-diary-extraction}"

API_SERVICE="${API_SERVICE:-site-diary-api}"
WEB_SERVICE="${WEB_SERVICE:-site-diary-web}"
MIGRATE_JOB="${MIGRATE_JOB:-site-diary-migrate}"
ALERTS_JOB="${ALERTS_JOB:-site-diary-permit-alerts}"

API_SA_EMAIL="${API_SA_EMAIL:-site-diary-api-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
WEB_SA_EMAIL="${WEB_SA_EMAIL:-site-diary-web-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
SCHEDULER_SA_EMAIL="${SCHEDULER_SA_EMAIL:-site-diary-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com}"

API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/api:${IMAGE_TAG}"
WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/web:${IMAGE_TAG}"
TASKS_QUEUE_PATH="projects/${PROJECT_ID}/locations/${REGION}/queues/${TASKS_QUEUE}"
CLOUDSQL_CONNECTION="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"

echo "==> [1/6] Building and pushing container images (tag: ${IMAGE_TAG})..."
gcloud builds submit ./services/api --tag="${API_IMAGE}" --project="${PROJECT_ID}"
gcloud builds submit ./apps/web --tag="${WEB_IMAGE}" --project="${PROJECT_ID}"

echo "==> [2/6] Running Alembic database migrations via Cloud Run Job '${MIGRATE_JOB}'..."
if gcloud run jobs describe "${MIGRATE_JOB}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud run jobs update "${MIGRATE_JOB}" \
    --image="${API_IMAGE}" \
    --region="${REGION}" \
    --service-account="${API_SA_EMAIL}" \
    --set-cloudsql-instances="${CLOUDSQL_CONNECTION}" \
    --set-secrets="DATABASE_URL=site-diary-database-url:latest" \
    --command="uv" \
    --args="run,alembic,upgrade,head" \
    --project="${PROJECT_ID}"
else
  gcloud run jobs create "${MIGRATE_JOB}" \
    --image="${API_IMAGE}" \
    --region="${REGION}" \
    --service-account="${API_SA_EMAIL}" \
    --set-cloudsql-instances="${CLOUDSQL_CONNECTION}" \
    --set-secrets="DATABASE_URL=site-diary-database-url:latest" \
    --command="uv" \
    --args="run,alembic,upgrade,head" \
    --project="${PROJECT_ID}"
fi
gcloud run jobs execute "${MIGRATE_JOB}" --region="${REGION}" --wait --project="${PROJECT_ID}"

echo "==> [3/6] Deploying API Cloud Run service '${API_SERVICE}'..."
WEB_URL_EXISTING="$(gcloud run services describe "${WEB_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || true)"
CORS_ORIGINS_VAL="${CORS_ORIGINS:-${WEB_URL_EXISTING:-https://${WEB_SERVICE}-${PROJECT_ID}.a.run.app}}"
PUBLIC_API_URL_VAL="${PUBLIC_API_BASE_URL:-https://${API_SERVICE}-${PROJECT_ID}.a.run.app}"

gcloud run deploy "${API_SERVICE}" \
  --image="${API_IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${API_SA_EMAIL}" \
  --add-cloudsql-instances="${CLOUDSQL_CONNECTION}" \
  --min-instances=1 \
  --max-instances=10 \
  --cpu=1 \
  --memory=1Gi \
  --set-env-vars="ENV=${ENVIRONMENT},LOG_FORMAT=json,ENABLE_API_DOCS=false,ENABLE_DEV_SEED=false,STORAGE_BACKEND=gcs,GCS_BUCKET=${GCS_BUCKET},USE_MOCK_GEMINI=false,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=gemini-2.5-flash,CLOUD_TASKS_QUEUE_PATH=${TASKS_QUEUE_PATH},CLOUD_TASKS_INVOKER_SA_EMAIL=${API_SA_EMAIL},CORS_ORIGINS=${CORS_ORIGINS_VAL},PUBLIC_API_BASE_URL=${PUBLIC_API_URL_VAL},NOTIFIER=fcm" \
  --set-secrets="DATABASE_URL=site-diary-database-url:latest,JWT_SECRET=site-diary-jwt-secret:latest,MEDIA_URL_SIGNING_SECRET=site-diary-media-url-signing-secret:latest,CLOUD_TASKS_SHARED_SECRET=site-diary-cloud-tasks-shared-secret:latest,SCHEDULER_SHARED_SECRET=site-diary-scheduler-shared-secret:latest" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}"

API_URL="$(gcloud run services describe "${API_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

# Ensure Cloud Tasks callback and PUBLIC_API_BASE_URL match the actual deployed API HTTPS URL.
gcloud run services update "${API_SERVICE}" \
  --region="${REGION}" \
  --update-env-vars="PUBLIC_API_BASE_URL=${API_URL},CLOUD_TASKS_HANDLER_URL=${API_URL}/internal/tasks/extract" \
  --project="${PROJECT_ID}"

echo "==> [4/6] Deploying Web Cloud Run service '${WEB_SERVICE}'..."
gcloud run deploy "${WEB_SERVICE}" \
  --image="${WEB_IMAGE}" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${WEB_SA_EMAIL}" \
  --min-instances=0 \
  --max-instances=10 \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars="NODE_ENV=production,API_BASE_URL=${API_URL},SESSION_COOKIE_SECURE=true,NEXT_PUBLIC_DEMO_MODE=false" \
  --allow-unauthenticated \
  --project="${PROJECT_ID}"

WEB_URL="$(gcloud run services describe "${WEB_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

if [[ -z "${WEB_URL_EXISTING}" && -n "${WEB_URL}" ]]; then
  gcloud run services update "${API_SERVICE}" \
    --region="${REGION}" \
    --update-env-vars="CORS_ORIGINS=${WEB_URL}" \
    --project="${PROJECT_ID}"
fi

echo "==> [5/6] Updating daily permit alerts Cloud Run Job '${ALERTS_JOB}'..."
if gcloud run jobs describe "${ALERTS_JOB}" --region="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud run jobs update "${ALERTS_JOB}" \
    --image="${API_IMAGE}" \
    --region="${REGION}" \
    --service-account="${API_SA_EMAIL}" \
    --set-cloudsql-instances="${CLOUDSQL_CONNECTION}" \
    --set-env-vars="ENV=${ENVIRONMENT},LOG_FORMAT=json,NOTIFIER=fcm" \
    --set-secrets="DATABASE_URL=site-diary-database-url:latest,JWT_SECRET=site-diary-jwt-secret:latest,MEDIA_URL_SIGNING_SECRET=site-diary-media-url-signing-secret:latest" \
    --command="uv" \
    --args="run,python,-m,app.jobs.permit_alerts" \
    --project="${PROJECT_ID}"
else
  gcloud run jobs create "${ALERTS_JOB}" \
    --image="${API_IMAGE}" \
    --region="${REGION}" \
    --service-account="${API_SA_EMAIL}" \
    --set-cloudsql-instances="${CLOUDSQL_CONNECTION}" \
    --set-env-vars="ENV=${ENVIRONMENT},LOG_FORMAT=json,NOTIFIER=fcm" \
    --set-secrets="DATABASE_URL=site-diary-database-url:latest,JWT_SECRET=site-diary-jwt-secret:latest,MEDIA_URL_SIGNING_SECRET=site-diary-media-url-signing-secret:latest" \
    --command="uv" \
    --args="run,python,-m,app.jobs.permit_alerts" \
    --project="${PROJECT_ID}"
fi

gcloud run jobs add-iam-policy-binding "${ALERTS_JOB}" \
  --region="${REGION}" \
  --member="serviceAccount:${SCHEDULER_SA_EMAIL}" \
  --role="roles/run.invoker" \
  --project="${PROJECT_ID}" >/dev/null

echo "==> [6/6] Running post-deployment readiness checks..."
curl -fsS --retry 3 --retry-delay 3 "${API_URL}/readyz"
echo ""
curl -fsS --retry 3 --retry-delay 3 "${WEB_URL}/api/health"
echo ""
echo "Deployment succeeded:"
echo "  API: ${API_URL}"
echo "  Web: ${WEB_URL}"
