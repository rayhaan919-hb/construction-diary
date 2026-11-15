# Data Processing Policy (DPA Baseline) — Construction Diary

**Effective Date:** 2026-11-15

---

## 1. Roles & Instructions

Customer (Organization workspace owner) acts as **Controller** of construction field records. Licensor / Operator acts as **Processor**, processing Customer personal data solely to provide Construction Diary synchronization, AI structuring, storage, PDF generation, and alerting services.

---

## 2. Technical & Organizational Security Measures

1. **Multi-Tenant Isolation:** Every project, log, permit, invitation, and upload ticket is scoped strictly by `organization_id` and verified server-side per request.
2. **Encryption in Transit & at Rest:** Release mobile and web traffic mandates TLS (`https://`); web cookies are signed and HttpOnly; mobile session tokens use Android Keystore `AES/GCM/NoPadding`; Cloud SQL and GCS encrypt data at rest using platform encryption.
3. **Upload Ticket & Content Verification:** Binary uploads require signed single-use tickets bound to `(user_id, project_id, object_id)` plus magic-byte inspection and byte-size caps (`25 MB`).
4. **Access Control & Auditability:** Role changes, logins, password resets, invitations, and deletions write append-only records in `audit_logs`.

---

## 3. Sub-Processors

| Sub-Processor | Purpose | Data Categories |
|---|---|---|
| Google Cloud Platform (Cloud Run, Cloud SQL, GCS, Cloud Tasks) | Application runtime, PostgreSQL hosting, encrypted object storage | Account metadata, logs, media, permits |
| Google Vertex AI (`aiplatform.googleapis.com`) | Structured transcription/extraction from audio, notes, images, and permit documents | Uploaded audio/text/document artifacts |
| Firebase Cloud Messaging | Push notifications for permit expiry & AI updates | Device registration tokens |
| Stripe (when enabled) | Subscription checkout and webhook billing state | Billing customer ID, plan tier |

---

## 4. Incident Notification & Data Subject Rights

Security incidents confirming unauthorized disclosure of Customer personal data will be notified promptly through the maintainer channel (`rayhaan919@gmail.com`). Workspace owners can export and delete organizational records via `/v1/organization/export` and `/v1/organization/delete`.
