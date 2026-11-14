from __future__ import annotations

import hashlib
import hmac
import re
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ProblemException
from app.db.models import Organization, Project, User

PLAN_QUOTAS: dict[str, dict[str, int]] = {
    "FREE": {
        "max_projects": 2,
        "max_seats": 5,
        "max_storage_bytes": 1_073_741_824,  # 1 GB
        "max_ai_extractions_monthly": 100,
    },
    "STARTER": {
        "max_projects": 25,
        "max_seats": 50,
        "max_storage_bytes": 53_687_091_200,  # 50 GB
        "max_ai_extractions_monthly": 1_000,
    },
    "PRO": {
        "max_projects": 100,
        "max_seats": 250,
        "max_storage_bytes": 536_870_912_000,  # 500 GB
        "max_ai_extractions_monthly": 10_000,
    },
    "ENTERPRISE": {
        "max_projects": 10_000,
        "max_seats": 10_000,
        "max_storage_bytes": 5_497_558_138_880,  # 5 TB
        "max_ai_extractions_monthly": 250_000,
    },
}


def apply_plan_quotas(org: Organization, plan_tier: str) -> None:
    quotas = PLAN_QUOTAS.get(plan_tier, PLAN_QUOTAS["STARTER"])
    org.plan_tier = plan_tier
    org.max_projects = quotas["max_projects"]
    org.max_seats = quotas["max_seats"]
    org.max_storage_bytes = quotas["max_storage_bytes"]
    org.max_ai_extractions_monthly = quotas["max_ai_extractions_monthly"]


def slugify_company_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug[:64] or "company"


def ensure_org_active(org: Organization | None) -> Organization:
    if org is None or org.deleted_at is not None:
        raise ProblemException(
            status_code=403,
            code="ORGANIZATION_UNAVAILABLE",
            title="Organization Unavailable",
            detail="Organization account does not exist or has been deleted",
        )
    if org.status == "SUSPENDED":
        raise ProblemException(
            status_code=403,
            code="ORGANIZATION_SUSPENDED",
            title="Account Suspended",
            detail="This organization is suspended. Contact your administrator or billing owner.",
        )
    if org.status == "PENDING_DELETION":
        raise ProblemException(
            status_code=403,
            code="ORGANIZATION_PENDING_DELETION",
            title="Account Scheduled for Deletion",
            detail="This organization is scheduled for deletion and read-only restricted.",
        )
    return org


def enforce_project_quota(db: Session, org: Organization) -> None:
    active_count = (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(
                Project.organization_id == org.id,
                Project.deleted_at.is_(None),
            )
        )
        or 0
    )
    if active_count >= org.max_projects:
        raise ProblemException(
            status_code=402,
            code="QUOTA_EXCEEDED_PROJECTS",
            title="Project Quota Exceeded",
            detail=f"Plan '{org.plan_tier}' allows up to {org.max_projects} active projects.",
        )


def enforce_seat_quota(db: Session, org: Organization) -> None:
    active_seats = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.organization_id == org.id,
                User.status == "ACTIVE",
            )
        )
        or 0
    )
    if active_seats >= org.max_seats:
        raise ProblemException(
            status_code=402,
            code="QUOTA_EXCEEDED_SEATS",
            title="Seat Quota Exceeded",
            detail=f"Plan '{org.plan_tier}' allows up to {org.max_seats} active users.",
        )


def enforce_storage_quota(org: Organization, additional_bytes: int) -> None:
    if (int(org.storage_bytes_used or 0) + additional_bytes) > org.max_storage_bytes:
        raise ProblemException(
            status_code=402,
            code="QUOTA_EXCEEDED_STORAGE",
            title="Storage Quota Exceeded",
            detail="Organization storage quota has been reached. Upgrade your plan.",
        )


def enforce_ai_quota(org: Organization) -> None:
    current_month = datetime.now(UTC).strftime("%Y-%m")
    used = (
        int(org.ai_extractions_this_month or 0)
        if org.billing_month == current_month
        else 0
    )
    if used >= org.max_ai_extractions_monthly:
        raise ProblemException(
            status_code=402,
            code="QUOTA_EXCEEDED_AI",
            title="AI Extraction Quota Exceeded",
            detail="Monthly AI extraction quota exceeded. Upgrade plan to process additional jobs.",
        )


def verify_stripe_webhook_signature(
    payload_bytes: bytes,
    sig_header: str,
    settings: Settings,
) -> bool:
    """Verify Stripe Webhook Stripe-Signature header (HMAC-SHA256 + replay timestamp window)."""
    secret = settings.STRIPE_WEBHOOK_SECRET.strip()
    if not secret:
        return False
    timestamp: int | None = None
    signatures: list[str] = []
    for part in sig_header.split(","):
        k, _, v = part.strip().partition("=")
        if k == "t":
            try:
                timestamp = int(v)
            except ValueError:
                return False
        elif k == "v1":
            signatures.append(v)

    if timestamp is None or not signatures:
        return False

    now = int(time.time())
    if abs(now - timestamp) > settings.BILLING_WEBHOOK_MAX_AGE_SECONDS:
        return False

    signed_payload = f"{timestamp}.".encode() + payload_bytes
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def resolve_org_for_project_or_user(
    db: Session, *, user: User | None = None, project: Project | None = None
) -> Organization | None:
    org_id: UUID | None = None
    if project is not None and project.organization_id is not None:
        org_id = project.organization_id
    elif user is not None and user.organization_id is not None:
        org_id = user.organization_id
    if org_id is None:
        return None
    return db.get(Organization, org_id)
