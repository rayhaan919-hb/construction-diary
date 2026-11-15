# Privacy Policy — Construction Diary

**Effective Date:** 2026-11-15  
**Product:** Construction Diary Web Portal, Backend API, and Android Field Application  
**Proprietor:** rayhaan919-hb (`rayhaan919@gmail.com`)

---

## 1. Scope & Controller Relationship

Construction Diary provides multi-tenant workspace software for construction organizations ("Customer" or "Controller") to capture daily site progress logs, voice memos, site photographs, and compliance permit records. For customer-submitted site records, the Customer organization acts as Data Controller and the Operator acts as Data Processor under the Data Processing Policy.

---

## 2. Categories of Data Processed

1. **Account & Identity Data:** Full name, work email address, hashed password credentials (Argon2id), assigned organization/project role, and preferred UI language (`en`, `ur`, `ar`).
2. **Field Site Records:** Daily typed progress notes, M4A voice recordings, structured tasks/labor/material/blocker summaries, JPEG site photographs, and municipal/safety permit metadata and scans.
3. **Location EXIF Metadata (Project-Controlled):** Site photos automatically strip EXIF location metadata on-device unless `allow_photo_gps` is explicitly enabled by the Customer's project owner.
4. **Device & Notification Tokens:** Firebase Cloud Messaging (FCM) device registration tokens stored encrypted (`AES-GCM`) on-device and cleared upon sign-out.
5. **Security & Audit Logs:** IP address, user-agent string, timestamp, actor user ID, and resource actions stored in immutable `audit_logs` for tenant compliance and intrusion detection.

---

## 3. Purpose & Legal Basis

- Delivering offline-first synchronization, voice/document AI extraction, daily PDF reporting, and permit expiry notifications.
- Enforcing tenant isolation, preventing brute-force authentication abuse, and maintaining verifiable security audit trails.

---

## 4. Storage, Sub-Processors & Retention

- **Cloud Hosting & Storage:** Google Cloud Platform (Cloud Run, Cloud SQL PostgreSQL, Cloud Storage private buckets with uniform access control, Secret Manager).
- **AI Processing:** Google Vertex AI / Gemini when enabled in production; raw audio and uploaded documents remain within tenant-isolated storage keys.
- **Billing:** Stripe (when enabled by Customer billing configuration; card details are never stored directly by Construction Diary).
- **Retention & Deletion:** Workspace owners can trigger workspace JSON export (`GET /v1/organization/export`) and organization deletion (`POST /v1/organization/delete`). Soft-deleted sync tombstones propagate across devices and remove cached media files.

---

## 5. Security Controls & Contact

All access/refresh cookies use signed HttpOnly attributes on the Web BFF, production Android releases enforce HTTPS and Android Keystore encryption, and server startup fails closed on insecure secrets.

Privacy inquiries: `rayhaan919@gmail.com`.
