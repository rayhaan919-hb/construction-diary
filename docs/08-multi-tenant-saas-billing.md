# 08 — Multi-Tenant SaaS Billing, Quotas & Audit Logging

---

## Organization Workspaces & Self-Service Registration

- `POST /v1/organizations/register` creates a new tenant `Organization`, initial `ORG_OWNER` user, and `OrganizationMember` inside one atomic SQLAlchemy transaction (`services/api/app/api/routes/saas.py`).
- Teams grow via tokenized time-limited email/invite-link invitations (`OrganizationInvitation`, `/v1/organization/invitations` and `/v1/invitations/accept`).

---

## Plan Tiers & Hard Quotas (`services/api/app/services/saas.py`)

| Tier | Default Seat Limit | Default Project Limit | Default Storage Quota |
|---|---|---|---|
| `STARTER` | Plan-managed Starter quotas | Starter project cap | Starter MB limit |
| `PRO` | Expanded Pro team seats | Multi-site project cap | Expanded storage MB |
| `ENTERPRISE` | Enterprise seat allocation | High-scale project allocation | Enterprise storage MB |

Quotas are enforced **transactionally before resource creation**:
- `enforce_seat_quota()` on invitation acceptance and member creation.
- `enforce_project_quota()` on `POST /v1/projects`.
- `enforce_storage_quota()` on `POST /v1/media/upload-url`.

---

## Stripe Billing & Replay-Protected Webhooks

- `POST /v1/billing/checkout` initiates Stripe Checkout Sessions using environment-configured `STRIPE_SECRET_KEY` and price IDs (`STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_ENTERPRISE`).
- `POST /v1/billing/webhook` verifies `Stripe-Signature` HMAC timestamps (`verify_stripe_webhook_signature`, max age `BILLING_WEBHOOK_MAX_AGE_SECONDS=300`) and deduplicates event IDs via the `billing_events` table so replayed webhooks are safely idempotent.

---

## Audit Trail, Export & Lifecycle Controls

- Sensitive actions (logins, password resets, invitations, role modifications, plan changes, media completions, project deletions) emit `AuditLog` entries queryable by `ORG_ADMIN`/`ORG_OWNER` at `/v1/organization/audit-logs`.
- `GET /v1/organization/export` exports tenant metadata and project logs.
- `POST /v1/organization/suspend` immediately suspends the tenant and revokes active refresh tokens across all org members; `POST /v1/organization/unsuspend` restores access; `POST /v1/organization/delete` requires exact `confirm_slug` verification.
