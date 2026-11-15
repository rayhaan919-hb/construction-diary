# 04 — Authentication, RBAC & Multi-Tenant Isolation

---

## Password Hashing & Credential Defense

Implemented in `services/api/app/services/auth.py`:
- **Algorithm:** Argon2id via `argon2.PasswordHasher()` with per-hash random salts.
- **Transparent Upgrade:** Legacy hashes trigger `needs_password_rehash()` during login and are upgraded cleanly in the same database transaction.
- **Timing Normalization:** Unknown emails run `verify_dummy_password()` to prevent user enumeration via response latency.
- **Account Lockout:** Repeated failed logins increment per-user failure counters and enforce temporary lockouts (`LOGIN_RATE_LIMIT_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`).

---

## Token Lifecycle & Session Management

- **Access Tokens:** Signed HS256 JWTs (`typ=access`) containing `sub` (user UUID), `role`, `org_id`, `iss`, `aud`, `jti`, `iat`, `exp`. Short TTL (`ACCESS_TOKEN_TTL_SECONDS=900`).
- **Refresh Tokens:** High-entropy random tokens stored as SHA-256 digests (`refresh_tokens` table) tied to `family_id`, IP/User-Agent metadata, and `expires_at`.
- **Rotation & Reuse Detection:** Every `/v1/auth/refresh` atomically marks the presented token rotated (`replaced_by_id`) and creates a successor. Re-presenting an already-rotated token immediately revokes every token sharing that `family_id`.
- **Global Revocation Triggers:** Changing password, confirming password reset, `/v1/auth/logout-all`, user removal from an organization, and organization suspension revoke refresh sessions.

---

## Dual-Layer RBAC Model

### 1. Organization Roles (`organization_members.role`)
- `ORG_OWNER`: Full billing, plan changes, suspension, export, deletion, member role management, and audit viewing.
- `ORG_ADMIN`: Workspace settings, team invitations, audit logs, project creation.
- `PROJECT_MANAGER`: Cross-project coordination and project creation within plan quotas.
- `SUPERVISOR` / `MEMBER`: Assigned project access based on `project_members`.

### 2. Project Roles (`project_members.role`)
- `OWNER`: Full read/write/delete within the project, team assignments, summary approvals, permit management.
- `SUPERVISOR`: Create/edit daily site logs, upload voice notes & photos, add/update permits, view project timeline.
- `VIEWER`: Read-only access to projects, timelines, permits, and reports.

---

## Tenant Boundary Enforcement

- All project routes resolve membership via `require_active_project_member()` (`services/api/app/api/deps.py`), verifying:
  1. Active non-deleted `User`.
  2. Active organization status (`Organization.status == 'ACTIVE'`).
  3. Active `Project` (`deleted_at IS NULL`) belonging to the caller's active organization.
  4. Active `ProjectMember` row for `(project_id, user_id)` with `deleted_at IS NULL`.
- All SaaS mutation actions record immutable `AuditLog` entries (`record_audit_event`) capturing `actor_user_id`, `organization_id`, `action`, `target_type`, `target_id`, IP address, and user agent.
