# 01 — Architecture Overview

Construction Diary is a three-tier offline-first platform engineered for construction owners, project managers, and field supervisors.

---

## High-Level Topology

```text
  +-----------------------------+         +---------------------------------+
  | Android Field App (Kotlin)  |         | Web Owner Portal (Next.js BFF)  |
  | - Jetpack Compose UI        |         | - HttpOnly JWT Session Cookies  |
  | - Room SQLite + File Cache  |         | - CSRF-protected BFF routes     |
  | - SyncEngine + WorkManager  |         | - Bilingual PDF report builder  |
  +--------------+--------------+         +----------------+----------------+
                 | HTTPS (JSON + Signed Media PUT)         | HTTPS (/api/bff -> FastAPI)
                 v                                         v
  +-------------------------------------------------------------------------+
  | Backend API (FastAPI + SQLAlchemy 2 + Alembic)                         |
  | - Auth & Sessions (Argon2 + JWT + Refresh Rotation)                     |
  | - Multi-Tenant SaaS (Orgs, Invites, Quotas, Stripe Billing, Audit Logs) |
  | - Cursor-Based Delta Sync (/v1/sync/push, /v1/sync/pull)                |
  | - Signed Media Tickets (/v1/media/upload-url, /v1/media/complete)       |
  | - Durable AI Extraction Queue (Vertex AI Gemini + Cloud Tasks)          |
  +-------------------+-------------------------------+---------------------+
                      |                               |
                      v                               v
        +--------------------------+     +----------------------------+
        | PostgreSQL 16 (Cloud SQL)|     | Google Cloud Storage (GCS) |
        | - sync_events sequence   |     | - Private bucket + V4 URLs |
        | - extraction_jobs leases |     | - Versioning & CORS rules  |
        | - audit_logs & tickets   |     | - Audio, photos, permits   |
        +--------------------------+     +----------------------------+
```

---

## Core Design Principles

1. **Offline-First Field Reliability:** Field supervisors create and edit site logs, capture photos, record Urdu/English/Arabic voice memos, and update permits with zero network connectivity. Local Room mutations enqueue automatically for background sync via `SyncWorker` and `MediaUploadWorker`.
2. **Event-Sourced Cursor Synchronization:** Every project-scoped mutation writes a monotonic entry into `sync_events`. Clients resume deterministically from their last committed integer cursor and handle conflicts without overwriting dirty offline changes.
3. **Strict Multi-Tenant Isolation:** Every organization workspace isolates projects, users, quotas, billing status, media tickets, and audit trails at both database and API dependency layers.
4. **Thin-Browser Web BFF:** The Next.js frontend keeps all access and refresh tokens inside signed server-only HttpOnly cookies and proxies API calls via `/api/bff/[...path]` with origin-verified CSRF checks.
5. **Dual Local/Cloud Execution:** The entire stack runs seamlessly locally (`LOCAL_STORAGE_DIR`, `USE_MOCK_GEMINI=true`, `NEXT_PUBLIC_DEMO_MODE=true`) as well as in hardened GCP production (`STORAGE_BACKEND=gcs`, Vertex AI Gemini, Cloud SQL, Secret Manager, Cloud Tasks).
