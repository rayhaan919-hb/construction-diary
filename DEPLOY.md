# Deployment Runbook (GCP Cloud Run + Cloud SQL + GCS + Cloud Scheduler)

This MVP was verified locally without provisioning cloud resources. Follow this runbook to deploy to Google Cloud Platform.

## 1. Prerequisites
- GCP project with billing enabled (`PROJECT_ID=...`, `REGION=us-central1`).
- Enable APIs:
  ```bash
  gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    storage.googleapis.com \
    cloudscheduler.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com
  ```

## 2. Cloud SQL (PostgreSQL 16)
```bash
gcloud sql instances create site-diary-pg \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=$REGION
gcloud sql databases create site_diary --instance=site-diary-pg
```
Run Alembic migrations against Cloud SQL (via Cloud SQL Auth Proxy):
```bash
cd services/api
DATABASE_URL="postgresql://postgres:<PASSWORD>@127.0.0.1:5432/site_diary" uv run alembic upgrade head
```

## 3. GCS Bucket & IAM
Create a private bucket for site audio, site photos, and permit documents:
```bash
gcloud storage buckets create gs://${PROJECT_ID}-site-diary-media --location=$REGION --uniform-bucket-level-access
```
Configure CORS on the bucket if web browsers ever PUT directly; mobile uses native OkHttp PUTs.
Grant the API service account:
- `roles/storage.objectAdmin` on the media bucket
- `roles/iam.serviceAccountTokenCreator` on itself (required for V4 signed URLs on Cloud Run)
- `roles/aiplatform.user` (for Vertex AI Gemini multimodal extraction)
- `roles/cloudsql.client`

## 4. Secrets
Store `JWT_SECRET` and `MEDIA_URL_SIGNING_SECRET` in Secret Manager and mount them as environment variables on Cloud Run.

## 5. Deploy API (`services/api`)
```bash
gcloud run deploy site-diary-api \
  --source=./services/api \
  --region=$REGION \
  --add-cloudsql-instances=${PROJECT_ID}:${REGION}:site-diary-pg \
  --set-env-vars="STORAGE_BACKEND=gcs,GCS_BUCKET=${PROJECT_ID}-site-diary-media,USE_MOCK_GEMINI=false,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=gemini-2.5-flash,NOTIFIER=email,fcm" \
  --allow-unauthenticated
```
Note: In production with Cloud Run scale-to-zero, prefer `min-instances=1` (or Cloud Tasks) so in-process `BackgroundTasks` extraction jobs complete cleanly.

## 6. Deploy Web (`apps/web`)
```bash
gcloud run deploy site-diary-web \
  --source=./apps/web \
  --region=$REGION \
  --set-env-vars="API_BASE_URL=https://<api-cloud-run-url>,SESSION_COOKIE_SECURE=true" \
  --allow-unauthenticated
```

## 7. Daily Permit Expiry Cron (Cloud Run Job + Cloud Scheduler)
Create a Cloud Run Job using the API container image running:
```text
python -m app.jobs.permit_alerts
```
Schedule it daily (e.g. `0 7 * * *` `Asia/Karachi`):
```bash
gcloud scheduler jobs create http permit-alerts-daily \
  --location=$REGION \
  --schedule="0 7 * * *" \
  --time-zone="Asia/Karachi" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/site-diary-permit-alerts:run" \
  --http-method=POST \
  --oauth-service-account-email=<scheduler-sa>@${PROJECT_ID}.iam.gserviceaccount.com
```

## 8. Mobile (`apps/mobile`)
1. Place Firebase `google-services.json` in `apps/mobile/app/google-services.json` to enable FCM push alerts (the build automatically enables the Google Services Gradle plugin when that file exists).
2. Configure release `API_BASE_URL` pointing to the Cloud Run API URL.
