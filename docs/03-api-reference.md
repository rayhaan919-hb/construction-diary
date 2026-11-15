# 03 — API Reference (`services/api`)

All API routes return standardized RFC 7807 `application/problem+json` error payloads (`{ type, title, status, detail, code, request_id }`) managed by `app/core/errors.py`.

---

## Authentication & Sessions (`/v1/auth`)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/auth/login` | Authenticate email/password & issue token pair | Public (rate limited + lockout) |
| `POST` | `/v1/auth/refresh` | Rotate refresh token & issue new access token | Refresh Token |
| `POST` | `/v1/auth/logout` | Revoke current refresh token family | Bearer |
| `POST` | `/v1/auth/logout-all` | Revoke all active sessions for current user | Bearer |
| `GET` | `/v1/auth/sessions` | List active device/refresh sessions | Bearer |
| `DELETE` | `/v1/auth/sessions/{id}` | Revoke a specific session | Bearer |
| `POST` | `/v1/auth/change-password` | Verify current password, update hash, revoke other sessions | Bearer |
| `POST` | `/v1/auth/password-reset/request` | Generate timed reset token & dispatch SMTP email | Public (rate limited) |
| `POST` | `/v1/auth/password-reset/confirm` | Consume reset token, update password, revoke sessions | Public |
| `GET` / `PATCH` | `/v1/auth/me` | Fetch or update current user profile (`preferred_locale`, `full_name`) | Bearer |
| `POST` | `/v1/auth/device-tokens` | Register Android FCM device token | Bearer |

---

## Multi-Tenant SaaS & Organization (`/v1/organizations`, `/v1/organization`, `/v1/invitations`, `/v1/billing`)

| Method | Path | Purpose | Auth |
|---|---|---|---|
| `POST` | `/v1/organizations/register` | Create new organization workspace + initial `ORG_OWNER` | Public |
| `GET` / `PATCH` | `/v1/organization` | View or update active org name/slug | `ORG_ADMIN` / `ORG_OWNER` |
| `GET` | `/v1/organization/usage` | Current seats, projects, storage usage vs plan quotas | Member |
| `POST` | `/v1/organization/subscription` | Update plan tier (`STARTER`, `PRO`, `ENTERPRISE`) | `ORG_OWNER` |
| `GET` | `/v1/organization/members` | List org members and roles | `ORG_ADMIN` / `ORG_OWNER` |
| `PATCH` / `DELETE` | `/v1/organization/members/{user_id}` | Update role or remove member (revokes memberships) | `ORG_OWNER` |
| `GET` / `POST` / `DELETE` | `/v1/organization/invitations` | List, issue, or revoke pending team invitations | `ORG_ADMIN` / `ORG_OWNER` |
| `POST` | `/v1/invitations/accept` | Accept invitation & join organization | Public |
| `GET` | `/v1/organization/audit-logs` | Paginated security/mutation audit trail | `ORG_ADMIN` / `ORG_OWNER` |
| `GET` | `/v1/organization/export` | Export tenant JSON snapshot | `ORG_OWNER` |
| `POST` | `/v1/organization/suspend` / `unsuspend` / `delete` | Org lifecycle controls | `ORG_OWNER` |
| `POST` | `/v1/billing/checkout` | Start Stripe checkout session (when Stripe configured) | `ORG_OWNER` |
| `POST` | `/v1/billing/webhook` | Signed Stripe webhook receiver (replay-protected) | Stripe HMAC |

---

## Projects, Logs, Permits & Reporting

| Method | Path | Purpose |
|---|---|---|
| `GET` / `POST` | `/v1/projects` | List tenant projects (paginated) or create project (quota checked) |
| `GET` / `PATCH` / `DELETE` | `/v1/projects/{id}` | Project detail, update, or soft delete |
| `GET` / `POST` / `DELETE` | `/v1/projects/{id}/members` | Manage project-level roles (`OWNER`, `SUPERVISOR`, `VIEWER`) |
| `GET` | `/v1/projects/{id}/timeline` | Cursor-paginated chronological daily timeline |
| `GET` | `/v1/projects/{id}/reports/daily` | Daily aggregated labor/tasks/materials/blockers summary + logs/permits |
| `GET` / `POST` | `/v1/projects/{id}/permits` | List/create project permits |
| `PATCH` / `DELETE` | `/v1/permits/{id}` | Update permit metadata or soft-delete |
| `PATCH` / `DELETE` | `/v1/logs/{id}` | Edit structured summary/notes or soft-delete log |
| `POST` | `/v1/logs/{id}/extract` | Queue durable Gemini AI extraction job |

---

## Sync, Media & System Probes

- `POST /v1/sync/push` — Idempotent batched push (permits, site logs, photo attachments) returning `APPLIED`, `CONFLICT`, or structured error codes per item.
- `GET /v1/sync/pull` — Cursor-based delta pull (`since`, `limit`, optional `project_id` backfill).
- `POST /v1/media/upload-url` & `POST /v1/media/complete` — Ticketed upload initiation + SHA-256/magic-byte verification.
- `POST /internal/tasks/extract` — Authenticated Cloud Tasks worker callback for AI extraction jobs.
- `GET /healthz`, `GET /readyz`, `GET /metrics` — Liveness, DB/storage readiness probe, and runtime counters.
