# Cookie Policy — Construction Diary Web Portal

**Effective Date:** 2026-11-15

---

## 1. Strict Functional Cookie Architecture

The Construction Diary Web Owner Portal (`apps/web`) does **not** use third-party advertising cookies, behavioral trackers, or cross-site analytics cookies. Cookies are used exclusively for authentication session security in Backend-for-Frontend (BFF) mode.

---

## 2. Cookies Used

| Cookie Name | Attributes | Purpose | Lifetime |
|---|---|---|---|
| `sd_access` | `HttpOnly`, `SameSite=Lax`, `Secure` (production) | Carries short-lived signed JWT access session to Next.js BFF API routes | ~15 minutes |
| `sd_refresh` | `HttpOnly`, `SameSite=Lax`, `Secure` (production) | Carries opaque rotating refresh token strictly on server routes (`/api/auth/*`, `/api/bff/*`) | Up to 60 days (revoked on logout/rotation) |

- No authentication tokens are persisted in browser `localStorage` or `sessionStorage`.
- CSRF protection (`apps/web/src/lib/csrf.ts`) validates `Origin` / `Referer` and `Sec-Fetch-Site` headers alongside `SameSite=Lax` cookie attributes.

---

## 3. Managing Cookies

Disabling strictly necessary functional cookies in your browser prevents signing in to the Web Owner Portal (`apps/web`).
