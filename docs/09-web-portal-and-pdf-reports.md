# 09 — Web Portal (`apps/web`) & Bilingual PDF Reports

The Next.js App Router portal gives project owners and managers a desktop command center with zero exposure of raw bearer JWTs to client-side JavaScript.

---

## BFF Cookie Architecture

- Login (`POST /api/auth/login`), registration (`POST /api/auth/register`), invitation acceptance (`POST /api/auth/accept-invite`), and password resets (`POST /api/auth/password-reset/*`) set signed HttpOnly `SameSite=Lax` cookies (`sd_access`, `sd_refresh`).
- API calls from Client Components target `/api/bff/[...path]`, which validates CSRF headers (`verifyCsrfOrigin`), refreshes expiring access tokens transparently, strips sensitive cookies before forwarding, and bounds request bodies to 1 MB (`apps/web/src/app/api/bff/[...path]/route.ts`).
- `src/lib/bff-path.ts` normalizes percent-encoded segments and blocks traversal (`..`, non-`/v1/` prefixes).

---

## UI Capabilities

- **Portfolio Dashboard (`/`):** Project cards, permit expiry status chips, active site metrics, create-project dialog, and direct navigation to Organization Admin Console (`/organization`).
- **Project Command View (`/projects/[id]`):** Chronological timeline filterable by search query, date range, and extraction status; inline summary editing and human approval; site audio playback; permit management modal; and team roster management.
- **Organization Console (`/organization`):** Company profile editing, plan upgrades & Stripe checkout triggers, seat/project/storage quota meters, team invitations & member role management, audit log viewer, JSON workspace export, and suspension/deletion controls.

---

## Bilingual PDF Daily Reports & Demo Preview Mode

- `/api/reports/[projectId]/[date]/pdf` validates `YYYY-MM-DD` calendar dates, fetches daily report data, embeds bundled Latin + Nastaliq/Arabic fonts, renders structured tables and RTL Urdu transcripts cleanly with `pdf-lib`, and attaches compressed JPEG photos fetched through `fetchSafePhotoBytes()`.
- Setting `NEXT_PUBLIC_DEMO_MODE=true` enables full evaluation (portfolio, multilingual timeline logs, permits, organization management, and downloadable binary PDF exports) without running FastAPI or PostgreSQL.
