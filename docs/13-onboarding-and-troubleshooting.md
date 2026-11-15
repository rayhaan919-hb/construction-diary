# 13 — User & Admin Onboarding & Troubleshooting Guide

---

## Onboarding Checklist for a New Construction Company

1. **Workspace Registration:** Open `/register` on the Web Portal (or call `POST /v1/organizations/register`) with company name, owner name, email, and strong password.
2. **Create First Project:** From the Portfolio dashboard, create a construction site project with address, local timezone (e.g., `Asia/Karachi`), and photo GPS privacy preference.
3. **Invite Team Members:** Open `/organization` -> Team Invitations, invite engineers/supervisors (`SUPERVISOR`, `PROJECT_MANAGER`, or `VIEWER`), and assign them to specific projects.
4. **Field Mobile Sign-In:** Install the Android APK, sign in using the invited credentials, toggle preferred language (`English`, `Urdu`, `Arabic`), and record/capture logs online or offline.

---

## Common Troubleshooting

### Backend fails startup with `Unsafe runtime configuration`
- Cause: `ENV=production` or `ENV=staging` detected missing/weak `JWT_SECRET`, identical `MEDIA_URL_SIGNING_SECRET`, wildcard `CORS_ORIGINS`, `ENABLE_DEV_SEED=true`, or `STORAGE_BACKEND=local`.
- Resolution: Supply distinct 32+ character secrets via Google Secret Manager / environment variables and review Section 2 of [`DEPLOY.md`](../DEPLOY.md).

### `pytest` invoked as `root` without `TEST_DATABASE_URL`
- Cause: PostgreSQL binaries refused execution as `root` in embedded `pgserver` mode.
- Resolution: Either run `pytest` as a non-root user or set `TEST_DATABASE_URL` to a running PostgreSQL instance (`postgresql://postgres:postgres@127.0.0.1:5432/site_diary_test`).

### Web PDF export fails on remote photo fetch
- Cause: Photo URL resolves to a disallowed private/loopback/link-local IP or non-allowlisted scheme (`photo-fetcher.ts` SSRF protection), or upstream signed URL expired.
- Resolution: Verify `PUBLIC_API_BASE_URL` / GCS signed URL validity and ensure object keys reside within authorized storage domains.

### Android Sync shows `CONFLICT_PENDING` badge
- Cause: A web owner or another user updated the same site log on the server while the Android device was offline.
- Resolution: Review the preserved offline notes inside `LogDetailScreen`, re-save notes to increment local mutation sequence cleanly, and tap **Sync Now**.
