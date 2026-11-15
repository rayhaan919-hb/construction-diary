# Terms of Service — Construction Diary

**Effective Date:** 2026-11-15  
**Product:** Construction Diary Commercial SaaS Platform

---

## 1. Agreement & License Relationship

By deploying or accessing Construction Diary, Customer agrees to these Terms of Service in conjunction with the written Commercial License Agreement executed under root [LICENSE](../../LICENSE). Nothing in these Terms grants Customer redistribution, sublicensing, or unauthorized multi-tenant resale rights.

---

## 2. Organization Accounts & Administration

1. **Workspace Registration:** Organization creation establishes an initial `ORG_OWNER` responsible for user provisioning, role assignment, project photo GPS policies, and billing compliance.
2. **Access Credentials:** Customers must enforce unique accounts per employee and rotate compromised credentials immediately using `/change-password` or `/v1/auth/logout-all`.
3. **Plan Quotas:** Subscription tiers (`STARTER`, `PRO`, `ENTERPRISE`) enforce configured seat, project, storage, and AI extraction ceilings (`services/api/app/services/saas.py`).

---

## 3. Customer Content & Compliance Permits

Customer retains all ownership rights to construction logs, voice notes, photographs, permit scans, and exported PDF reports. Construction Diary is a record-keeping and workflow tool and does not issue legal engineering sign-off or guarantee municipal permit approval.

---

## 4. Service Availability, Suspension & Termination

- **Suspension:** Workspaces showing billing delinquency, security abuse, or administrative suspension (`POST /v1/organization/suspend`) immediately revoke active refresh sessions until restored.
- **Export & Termination:** `ORG_OWNER` users may export tenant records at any time before requesting lifecycle deletion (`POST /v1/organization/delete`).

---

## 5. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, LIABILITY SHALL NOT EXCEED FEES PAID UNDER THE APPLICABLE COMMERCIAL AGREEMENT DURING THE PRECEDING TWELVE (12) MONTHS. SOFTWARE PROVIDED WITHOUT CUSTOM SLA IS GOVERNED BY THE DISCLAIMER IN ROOT `LICENSE`.
