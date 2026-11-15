# 06 — Media Pipeline & Security Model

Media handling covers construction voice memos (`AUDIO`), site progress images (`PHOTO`), and compliance permit scans (`PERMIT_DOC`).

---

## Upload Ticket Protocol

1. **Ticket Request (`POST /v1/media/upload-url`):**
   - Verifies active user, organization status, project membership, write role (`LOG_WRITE_ROLES` / `PERMIT_WRITE_ROLES`), and record ownership (`_verify_target_ownership_for_ticket` in `services/api/app/api/routes/media.py`).
   - Enforces organization storage quota (`enforce_storage_quota`) and `MAX_UPLOAD_BYTES` (25 MB limit).
   - Validates MIME type, file extension against safe allowlists, and generates an immutable UUID-based object path (`projects/{project_id}/{kind}/{object_id}/{uuid}.{ext}`), blocking path traversal via `sanitize_relative_object_key`.
   - Persists an `UploadTicket` row bound to `(user_id, project_id, kind, target_object_id, object_key, max_bytes, expires_at)` and returns a time-limited upload target (`gcs` V4 signed PUT URL or HMAC-signed local upload URL).

2. **Direct Binary PUT:**
   - Client uploads bytes directly to GCS or the signed local upload endpoint (`MediaUploader` in `apps/mobile` computes SHA-256 on stream).
   - Backend checks ticket signature, expiry, single-use status, object non-existence (prevents overwrite of already committed objects), size ceiling, and header magic bytes (`validate_magic_bytes`).

3. **Upload Completion (`POST /v1/media/complete`):**
   - Verifies ticket ownership, project match, unreadiness of prior completion (replay defense), stored object presence, SHA-256 match (when supplied), and magic bytes on storage.
   - Atomically marks `UploadTicket.consumed_at`, transitions entity status (`UPLOADED`), updates org storage bytes, and for `AUDIO` enqueues a durable AI extraction job.

---

## Download & Web PDF SSRF Protection

- Signed GET URLs are minted dynamically with `SIGNED_URL_TTL_SECONDS=900` so stored `storage_uri` strings never grant public access.
- When `apps/web` generates downloadable daily PDF reports (`apps/web/src/app/api/reports/[projectId]/[date]/pdf/route.ts`), `apps/web/src/lib/pdf/photo-fetcher.ts` inspects photo URLs before fetching:
  - Enforces URL allowlist and HTTPS (or explicit configured `API_BASE_URL`).
  - Performs DNS resolution checking (`dns.lookup(..., { all: true })`) and blocks loopback (`127.0.0.0/8`), RFC 1918 (`10/8`, `172.16/12`, `192.168/16`), CGNAT (`100.64/10`), cloud metadata/link-local (`169.254/16`, `fe80::/10`), and unique-local IPv6 (`fc00::/7`) targets.
