# Acceptable Use Policy — Construction Diary

**Effective Date:** 2026-11-15

---

## Permitted Use

Construction Diary is authorized solely for managing construction project field logs, worker attendance summaries, material tracking, site photography, permit expiry tracking, and authorized organizational administration.

---

## Prohibited Conduct

Customers and workspace users must **not**:
1. Upload malware, executable scripts, disguised binaries, or files outside supported media formats (verified via server-side magic-byte inspection).
2. Attempt cross-tenant enumeration, unauthorized IDOR access, upload-ticket replay, or automated brute-force login attempts.
3. Probe private/internal network endpoints via custom URLs or attempt SSRF against platform metadata services.
4. Misuse AI extraction endpoints for unrelated bulk audio/document processing outside authorized construction project quotas.
5. Share individual user credentials across multiple field personnel where project audit integrity (`audit_logs`) requires individual accountability.

Violations may result in immediate rate limiting, account lockout, workspace suspension (`POST /v1/organization/suspend`), or license termination.
