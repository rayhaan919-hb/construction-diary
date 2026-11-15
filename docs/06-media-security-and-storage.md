# 06 — Media Pipeline & Security Model

Media handling covers construction voice memos (`AUDIO`), site progress images (`PHOTO`), and compliance permit scans (`PERMIT_DOC`).

---

## Upload Reservation & Ticket Protocol

1. **Pending Record Reservation (`POST /v1/media/reservations`):**
   - For records that have not synchronized yet (`AUDIO`, `PHOTO`, `PERMIT_DOC`), clients register a short-lived `MediaReservation` bound to `(organization_id, user_id, project_id, kind, object_id)`.
   - Validates active user, organization status, project membership, and write role (`LOG_WRITE_ROLES` / `PERMIT_WRITE_ROLES`), plus prevents claiming records owned by other users.

2. **Ticket Request (`POST /v1/media/upload-url`):**
   - Verifies active user, organization status, project membership, write role, and target validity (`_check_existing_record_for_media` for existing records or an active matching `MediaReservation` for pending offline records). Rejects unclaimed/arbitrary `object_id` values.
   - Enforces organization storage quota (`enforce_storage_quota`), daily quota / per-user upload rate limits, and `MAX_UPLOAD_BYTES` (25 MB limit).
   - Validates MIME type, file extension against safe allowlists, and generates an immutable UUID-based object path (`projects/{project_id}/{kind}/{object_id}/{uuid}.{ext}`), blocking path traversal via `sanitize_relative_object_key`.
   - Persists an `UploadTicket` row bound to `(user_id, project_id, kind, target_object_id, object_key, max_bytes, expires_at)` and returns a time-limited upload target (`gcs` V4 signed PUT URL or HMAC-signed local upload URL).

3. **Direct Binary PUT:**
   - Client uploads bytes directly to GCS or the signed local upload endpoint (`MediaUploader` in `apps/mobile` computes SHA-256 on stream).
   - Backend checks ticket signature, expiry, single-use status, object non-existence (prevents overwrite of already committed objects), size ceiling, and header magic bytes (`validate_magic_bytes`).

4. **Upload Completion (`POST /v1/media/complete`):**
   - Verifies ticket ownership, project match, unreadiness of prior completion (idempotent replay handling for matching completed tickets; rejects mismatched tickets), stored object presence, SHA-256 match (when supplied), and magic bytes on storage.
   - Atomically marks `UploadTicket.consumed_at`, consumes matching `MediaReservation`, transitions entity status (`UPLOADED`), updates org storage bytes, and for `AUDIO` enqueues a durable AI extraction job.

---

## Auditable Orphan Cleanup

- Scheduled cleanup (`services/api/app/jobs/media_cleanup.py`, `services/api/app/services/media_cleanup.py`, and internal Cloud Run/Tasks endpoint `/v1/internal/tasks/media-cleanup`) expires stale `MediaReservation` and uncompleted `UploadTicket` records, deletes incomplete or aged unattached objects (outside a configurable grace window so active uploads and valid customer attachments remain safe), and prunes old failed `ExtractionJob` records.
- Every execution writes an auditable summary row to `media_cleanup_runs` (`0003_media_reservations.py`) and `audit_logs` (`action="media.cleanup.run"`).

---

## Download & Web PDF SSRF Protection

- Signed GET URLs are minted dynamically with `SIGNED_URL_TTL_SECONDS=900` so stored `storage_uri` strings never grant public access.
- When `apps/web` generates downloadable daily PDF reports (`apps/web/src/app/api/reports/[projectId]/[date]/pdf/route.ts`), `apps/web/src/lib/pdf/photo-fetcher.ts` inspects photo URLs before fetching:
  - Enforces URL allowlist and HTTPS (or explicit configured loopback `API_BASE_URL` in dev/Docker setups).
  - Performs DNS resolution checking (`dns.lookup(..., { all: true })`) and blocks loopback (`127.0.0.0/8`), RFC 1918 (`10/8`, `172.16/12`, `192.168/16`), CGNAT (`100.64/10`), cloud metadata/link-local (`169.254/16`, `fe80::/10`), and unique-local IPv6 (`fc00::/7`) targets (explicit configured loopback is permitted only when configured cleanly as local backend).
  - Browser CSP in `apps/web/src/lib/csp.ts` + `apps/web/src/proxy.ts` enforces strict `img-src`/`media-src 'self' data: blob: https:` in production while permitting only the exact configured loopback origin in local/Docker deployments.
