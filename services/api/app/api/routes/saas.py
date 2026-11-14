from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Annotated, Any, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import extract_client_meta, get_current_user, get_verified_user
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.permissions import (
    ORG_ADMIN_ROLES,
    ORG_AUDIT_VIEW_ROLES,
    ORG_OWNER_ROLES,
    Role,
    can_assign_project_role,
)
from app.core.rate_limit import rate_limiter
from app.db.models import (
    AuditLog,
    BillingEvent,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    Permit,
    Project,
    ProjectMember,
    SiteLog,
    SiteLogPhoto,
    User,
)
from app.db.session import get_db
from app.schemas.auth import TokenPairResponse, UserResponse
from app.schemas.saas import (
    AccountDeleteRequest,
    AuditLogItemResponse,
    AuditLogListResponse,
    BillingCheckoutResponse,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationResponse,
    OrganizationMemberResponse,
    OrganizationMemberRoleUpdateRequest,
    OrganizationPatchRequest,
    OrganizationRegisterRequest,
    OrganizationRegisterResponse,
    OrganizationResponse,
    OrganizationUsageResponse,
    OrgStatus,
    PlanTier,
    SubscriptionPlanChangeRequest,
    SubscriptionStatus,
)
from app.services.audit import record_audit_event
from app.services.auth import hash_password, issue_token_pair, revoke_all_user_sessions
from app.services.saas import (
    apply_plan_quotas,
    enforce_seat_quota,
    ensure_org_active,
    slugify_company_name,
    verify_stripe_webhook_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["saas"])


def _require_org_member(
    db: Session,
    user: User,
    *,
    allowed_roles: frozenset[str] | None = None,
    allow_suspended: bool = False,
) -> tuple[Organization, OrganizationMember]:
    if user.organization_id is None:
        raise ProblemException(
            status_code=403,
            code="NO_ORGANIZATION",
            title="Forbidden",
            detail="Your account is not associated with an organization",
        )
    org = db.get(Organization, user.organization_id)
    if org is None or org.deleted_at is not None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Organization not found",
        )
    if not allow_suspended:
        ensure_org_active(org)

    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.deleted_at.is_(None),
        )
    )
    role = membership.role if membership is not None else user.role
    if allowed_roles is not None and role not in allowed_roles:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient organization permissions for this action",
        )
    if membership is None:
        membership = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=role,
        )
    return org, membership


def _serialize_org(org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=cast(OrgStatus, org.status),
        plan_tier=cast(PlanTier, org.plan_tier),
        subscription_status=cast(SubscriptionStatus, org.subscription_status),
        billing_provider=org.billing_provider,
        billing_customer_id=org.billing_customer_id,
        billing_subscription_id=org.billing_subscription_id,
        trial_ends_at=org.trial_ends_at,
        current_period_end=org.current_period_end,
        max_projects=org.max_projects,
        max_seats=org.max_seats,
        max_storage_bytes=org.max_storage_bytes,
        max_ai_extractions_monthly=org.max_ai_extractions_monthly,
        ai_extractions_this_month=org.ai_extractions_this_month,
        storage_bytes_used=org.storage_bytes_used,
        billing_month=org.billing_month,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


def _send_invitation_email(
    recipient_email: str,
    company_name: str,
    raw_token: str,
    settings: Settings,
) -> None:
    if not settings.SMTP_HOST:
        return
    msg = EmailMessage()
    msg["Subject"] = f"You have been invited to join {company_name} on Site Diary"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient_email
    base = settings.cors_origin_list[0] if settings.cors_origin_list else ""
    invite_url = f"{base.rstrip('/')}/accept-invite?token={raw_token}" if base else raw_token
    msg.set_content(
        f"You have been invited to join {company_name} on Site Diary.\n\n"
        f"Accept invitation (token/link):\n{invite_url}\n"
    )
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


@router.post(
    "/v1/organizations/register",
    response_model=OrganizationRegisterResponse,
    status_code=201,
)
def register_organization(
    payload: OrganizationRegisterRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OrganizationRegisterResponse:
    ip_addr, user_agent = extract_client_meta(request)
    ip_decision = rate_limiter.check(
        f"org-register:ip:{ip_addr or 'unknown'}",
        max(5, settings.RATE_LIMIT_AUTH_PER_MINUTE // 2),
        60,
    )
    if not ip_decision.allowed:
        raise ProblemException(
            status_code=429,
            code="RATE_LIMITED",
            title="Too Many Requests",
            detail="Too many signup attempts; try again shortly.",
            headers={"Retry-After": str(ip_decision.retry_after_seconds)},
        )

    normalized_email = str(payload.owner_email).strip().lower()
    if db.scalar(select(User).where(func.lower(User.email) == normalized_email)) is not None:
        raise ProblemException(
            status_code=409,
            code="CONFLICT",
            title="Conflict",
            detail="An account with this email already exists",
        )

    base_slug = slugify_company_name(payload.company_slug or payload.company_name)
    slug = base_slug
    if db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        if payload.company_slug:
            raise ProblemException(
                status_code=409,
                code="CONFLICT",
                title="Conflict",
                detail="Company slug is already taken",
            )
        slug = f"{base_slug[:55]}-{secrets.token_hex(4)}"

    now = datetime.now(UTC)
    org = Organization(
        name=payload.company_name.strip(),
        slug=slug,
        status="ACTIVE",
        subscription_status="ACTIVE" if payload.plan_tier == "FREE" else "TRIALING",
        trial_ends_at=None if payload.plan_tier == "FREE" else now + timedelta(days=14),
        billing_month=now.strftime("%Y-%m"),
    )
    apply_plan_quotas(org, payload.plan_tier)
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.owner_full_name.strip(),
        role="OWNER",
        status="ACTIVE",
        preferred_locale=payload.preferred_locale,
        must_change_password=False,
        password_changed_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()

    org.created_by = user.id
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="OWNER",
        )
    )
    pair = issue_token_pair(
        db,
        user=user,
        device_label=user_agent or "web-signup",
        settings=settings,
    )
    record_audit_event(
        db,
        action="organization.register",
        resource_type="organization",
        resource_id=org.id,
        actor_user=user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"plan_tier": org.plan_tier, "slug": org.slug},
    )
    db.commit()
    db.refresh(org)
    db.refresh(user)

    return OrganizationRegisterResponse(
        organization=_serialize_org(org),
        user=UserResponse.model_validate(user),
        tokens=TokenPairResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            access_expires_in=pair.access_expires_in,
            refresh_expires_at=pair.refresh_expires_at,
            user=UserResponse.model_validate(user),
        ),
    )


@router.get("/v1/organization", response_model=OrganizationResponse)
def get_organization(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    org, _ = _require_org_member(db, current_user)
    return _serialize_org(org)


@router.patch("/v1/organization", response_model=OrganizationResponse)
def update_organization(
    payload: OrganizationPatchRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    if payload.name is not None:
        org.name = payload.name.strip()
        org.updated_at = datetime.now(UTC)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.update",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"name": org.name},
    )
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@router.get("/v1/organization/usage", response_model=OrganizationUsageResponse)
def get_organization_usage(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationUsageResponse:
    org, _ = _require_org_member(db, current_user)
    active_projects = (
        db.scalar(
            select(func.count())
            .select_from(Project)
            .where(Project.organization_id == org.id, Project.deleted_at.is_(None))
        )
        or 0
    )
    active_seats = (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.organization_id == org.id, User.status == "ACTIVE")
        )
        or 0
    )
    current_month = datetime.now(UTC).strftime("%Y-%m")
    used_ai = (
        int(org.ai_extractions_this_month or 0)
        if org.billing_month == current_month
        else 0
    )
    return OrganizationUsageResponse(
        organization_id=org.id,
        active_projects=int(active_projects),
        max_projects=org.max_projects,
        active_seats=int(active_seats),
        max_seats=org.max_seats,
        storage_bytes_used=int(org.storage_bytes_used or 0),
        max_storage_bytes=org.max_storage_bytes,
        ai_extractions_this_month=used_ai,
        max_ai_extractions_monthly=org.max_ai_extractions_monthly,
    )


@router.get("/v1/organization/members", response_model=list[OrganizationMemberResponse])
def list_organization_members(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrganizationMemberResponse]:
    org, _ = _require_org_member(db, current_user)
    rows = db.execute(
        select(User)
        .where(User.organization_id == org.id, User.status != "DELETED")
        .order_by(User.created_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars()
    return [
        OrganizationMemberResponse(
            organization_id=org.id,
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=cast(Role, u.role),
            status=u.status,
            created_at=u.created_at,
        )
        for u in rows
    ]


@router.patch(
    "/v1/organization/members/{user_id}",
    response_model=OrganizationMemberResponse,
)
def update_organization_member_role(
    user_id: UUID,
    payload: OrganizationMemberRoleUpdateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationMemberResponse:
    org, actor_member = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    if not can_assign_project_role(actor_member.role, payload.role):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail=f"Your role ({actor_member.role}) cannot assign role {payload.role}",
        )
    target_user = db.get(User, user_id)
    if (
        target_user is None
        or target_user.organization_id != org.id
        or target_user.status == "DELETED"
    ):
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Organization member not found",
        )
    if target_user.role == "OWNER" and payload.role != "OWNER":
        owner_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.organization_id == org.id,
                    User.role == "OWNER",
                    User.status == "ACTIVE",
                )
            )
            or 0
        )
        if owner_count <= 1:
            raise ProblemException(
                status_code=409,
                code="CONFLICT",
                title="Conflict",
                detail="Cannot demote the last active organization OWNER",
            )

    old_role = target_user.role
    target_user.role = payload.role
    org_member = db.get(OrganizationMember, (org.id, target_user.id))
    if org_member is not None and org_member.deleted_at is None:
        org_member.role = payload.role

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.member.role_change",
        resource_type="user",
        resource_id=target_user.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"old_role": old_role, "new_role": payload.role},
    )
    db.commit()
    db.refresh(target_user)
    return OrganizationMemberResponse(
        organization_id=org.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=target_user.role,
        status=target_user.status,
        created_at=target_user.created_at,
    )


@router.delete("/v1/organization/members/{user_id}", status_code=204)
def deactivate_organization_member(
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    target_user = db.get(User, user_id)
    if (
        target_user is None
        or target_user.organization_id != org.id
        or target_user.status == "DELETED"
    ):
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Organization member not found",
        )
    if target_user.role == "OWNER":
        owner_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.organization_id == org.id,
                    User.role == "OWNER",
                    User.status == "ACTIVE",
                )
            )
            or 0
        )
        if owner_count <= 1:
            raise ProblemException(
                status_code=409,
                code="CONFLICT",
                title="Conflict",
                detail="Cannot deactivate the last active organization OWNER",
            )

    target_user.status = "SUSPENDED"
    org_member = db.get(OrganizationMember, (org.id, target_user.id))
    if org_member is not None:
        org_member.deleted_at = datetime.now(UTC)
    revoke_all_user_sessions(db, target_user, bump_token_version=True)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.member.deactivate",
        resource_type="user",
        resource_id=target_user.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/v1/organization/invitations",
    response_model=InvitationResponse,
    status_code=201,
)
def create_invitation(
    payload: InvitationCreateRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvitationResponse:
    org, actor_member = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    if not can_assign_project_role(actor_member.role, payload.role):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail=f"Your role ({actor_member.role}) cannot invite with role {payload.role}",
        )
    enforce_seat_quota(db, org)

    normalized_email = str(payload.email).strip().lower()
    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing_user is not None and existing_user.organization_id not in (None, org.id):
        raise ProblemException(
            status_code=409,
            code="CONFLICT",
            title="Conflict",
            detail="Email belongs to an existing user in another organization",
        )

    if payload.project_id is not None:
        proj = db.get(Project, payload.project_id)
        if proj is None or proj.deleted_at is not None or proj.organization_id != org.id:
            raise ProblemException(
                status_code=404,
                code="NOT_FOUND",
                title="Not Found",
                detail="Target project not found in organization",
            )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    inv = OrganizationInvitation(
        organization_id=org.id,
        project_id=payload.project_id,
        email=normalized_email,
        full_name=payload.full_name.strip(),
        role=payload.role,
        token_hash=token_hash,
        invited_by=current_user.id,
        expires_at=now + timedelta(days=7),
    )
    db.add(inv)
    db.flush()

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.invitation.create",
        resource_type="invitation",
        resource_id=inv.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"invitee_email": normalized_email, "role": payload.role},
    )
    db.commit()
    db.refresh(inv)

    try:
        _send_invitation_email(normalized_email, org.name, raw_token, settings)
    except Exception:
        logger.warning("Failed sending invitation email for invitation=%s", inv.id)

    return InvitationResponse(
        id=inv.id,
        organization_id=inv.organization_id,
        project_id=inv.project_id,
        email=inv.email,
        full_name=inv.full_name,
        role=cast(Role, inv.role),
        expires_at=inv.expires_at,
        accepted_at=inv.accepted_at,
        revoked_at=inv.revoked_at,
        created_at=inv.created_at,
        invite_token=raw_token,
    )


@router.get("/v1/organization/invitations", response_model=list[InvitationResponse])
def list_invitations(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvitationResponse]:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    rows = db.scalars(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.organization_id == org.id)
        .order_by(OrganizationInvitation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        InvitationResponse(
            id=inv.id,
            organization_id=inv.organization_id,
            project_id=inv.project_id,
            email=inv.email,
            full_name=inv.full_name,
            role=cast(Role, inv.role),
            expires_at=inv.expires_at,
            accepted_at=inv.accepted_at,
            revoked_at=inv.revoked_at,
            created_at=inv.created_at,
        )
        for inv in rows
    ]


@router.delete("/v1/organization/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    inv = db.get(OrganizationInvitation, invitation_id)
    if inv is None or inv.organization_id != org.id:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Invitation not found",
        )
    if inv.revoked_at is None:
        inv.revoked_at = datetime.now(UTC)
    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.invitation.revoke",
        resource_type="invitation",
        resource_id=inv.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return Response(status_code=204)


@router.post("/v1/invitations/accept", response_model=TokenPairResponse)
def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    token_hash = hashlib.sha256(payload.token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    inv = db.scalar(
        select(OrganizationInvitation)
        .where(OrganizationInvitation.token_hash == token_hash)
        .with_for_update()
    )
    if (
        inv is None
        or inv.accepted_at is not None
        or inv.revoked_at is not None
        or inv.expires_at <= now
    ):
        raise ProblemException(
            status_code=400,
            code="INVALID_INVITATION_TOKEN",
            title="Invalid Invitation",
            detail="Invitation token is invalid, expired, or has already been used",
        )

    org = ensure_org_active(db.get(Organization, inv.organization_id))
    enforce_seat_quota(db, org)

    user = db.scalar(select(User).where(func.lower(User.email) == inv.email.lower()))
    if user is None:
        user = User(
            organization_id=org.id,
            email=inv.email,
            password_hash=hash_password(payload.password),
            full_name=inv.full_name,
            role=inv.role,
            status="ACTIVE",
            preferred_locale="en",
            must_change_password=False,
            password_changed_at=now,
            last_login_at=now,
        )
        db.add(user)
        db.flush()
    else:
        if user.organization_id not in (None, org.id):
            raise ProblemException(
                status_code=409,
                code="CONFLICT",
                title="Conflict",
                detail="Account already belongs to another organization",
            )
        user.organization_id = org.id
        user.password_hash = hash_password(payload.password)
        user.status = "ACTIVE"
        user.must_change_password = False
        user.password_changed_at = now
        user.last_login_at = now
        user.role = inv.role

    org_member = db.get(OrganizationMember, (org.id, user.id))
    if org_member is None:
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=inv.role))
    else:
        org_member.deleted_at = None
        org_member.role = inv.role

    if inv.project_id is not None:
        pm = db.get(ProjectMember, (inv.project_id, user.id))
        if pm is None:
            db.add(ProjectMember(project_id=inv.project_id, user_id=user.id, role=inv.role))
        else:
            pm.deleted_at = None
            pm.role = inv.role

    inv.accepted_at = now
    ip_addr, user_agent = extract_client_meta(request)
    pair = issue_token_pair(
        db,
        user=user,
        device_label=user_agent or "invite-accept",
        settings=settings,
    )
    record_audit_event(
        db,
        action="organization.invitation.accept",
        resource_type="invitation",
        resource_id=inv.id,
        actor_user=user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(user)
    return TokenPairResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        access_expires_in=pair.access_expires_in,
        refresh_expires_at=pair.refresh_expires_at,
        user=UserResponse.model_validate(user),
    )


@router.post("/v1/organization/subscription", response_model=OrganizationResponse)
def update_subscription_plan(
    payload: SubscriptionPlanChangeRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_OWNER_ROLES)
    old_plan = org.plan_tier
    apply_plan_quotas(org, payload.plan_tier)
    org.subscription_status = "ACTIVE"
    org.updated_at = datetime.now(UTC)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.subscription.change",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"old_plan": old_plan, "new_plan": payload.plan_tier},
    )
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@router.post("/v1/billing/checkout", response_model=BillingCheckoutResponse)
def create_billing_checkout_session(
    payload: SubscriptionPlanChangeRequest,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BillingCheckoutResponse:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_OWNER_ROLES)
    price_map = {
        "STARTER": settings.STRIPE_PRICE_STARTER,
        "PRO": settings.STRIPE_PRICE_PRO,
        "ENTERPRISE": settings.STRIPE_PRICE_ENTERPRISE,
    }
    price_id = price_map.get(payload.plan_tier, "").strip()
    if not settings.STRIPE_SECRET_KEY.strip() or not price_id:
        return BillingCheckoutResponse(
            provider="stripe",
            configured=False,
            checkout_url=None,
            message=(
                "Stripe external billing credentials are not configured yet; "
                "plan quotas can be managed internally or via Stripe environment variables."
            ),
        )

    base = settings.cors_origin_list[0].rstrip("/") if settings.cors_origin_list else "http://localhost:3000"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(settings.STRIPE_SECRET_KEY.strip(), ""),
            data={
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": f"{base}/organization?billing=success",
                "cancel_url": f"{base}/organization?billing=canceled",
                "client_reference_id": str(org.id),
                "metadata[organization_id]": str(org.id),
                "metadata[plan_tier]": payload.plan_tier,
                "customer_email": current_user.email,
            },
        )
    if resp.status_code >= 400:
        raise ProblemException(
            status_code=502,
            code="BILLING_PROVIDER_ERROR",
            title="Billing Provider Error",
            detail="Could not create Stripe Checkout session",
        )
    session_data = resp.json()
    return BillingCheckoutResponse(
        provider="stripe",
        configured=True,
        checkout_url=str(session_data.get("url") or ""),
        message="Checkout session created",
    )


@router.post("/v1/billing/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, Any]:
    raw_body = await request.body()
    if not stripe_signature or not verify_stripe_webhook_signature(
        raw_body, stripe_signature, settings
    ):
        raise ProblemException(
            status_code=400,
            code="INVALID_WEBHOOK_SIGNATURE",
            title="Invalid Signature",
            detail="Stripe webhook signature verification failed",
        )

    event: dict[str, Any] = await request.json()
    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("type") or "").strip()
    if not event_id or not event_type:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Malformed Stripe event payload",
        )

    data_obj = cast(dict[str, Any], (event.get("data") or {}).get("object") or {})
    meta = cast(dict[str, Any], data_obj.get("metadata") or {})
    org_id_raw = meta.get("organization_id") or data_obj.get("client_reference_id")
    org: Organization | None = None
    if org_id_raw:
        try:
            org = db.get(Organization, UUID(str(org_id_raw)))
        except ValueError:
            org = None
    if org is None and data_obj.get("customer"):
        org = db.scalar(
            select(Organization).where(
                Organization.billing_customer_id == str(data_obj["customer"])
            )
        )

    inserted = db.scalar(
        pg_insert(BillingEvent)
        .values(
            organization_id=org.id if org is not None else None,
            provider="stripe",
            external_event_id=event_id,
            event_type=event_type,
            payload={"id": event_id, "type": event_type, "object_id": data_obj.get("id")},
        )
        .on_conflict_do_nothing(index_elements=["external_event_id"])
        .returning(BillingEvent.id)
    )
    if inserted is None:
        return {"received": True, "duplicate": True}

    if org is not None:
        if event_type == "checkout.session.completed":
            tier = str(meta.get("plan_tier") or org.plan_tier)
            apply_plan_quotas(org, tier)
            org.subscription_status = "ACTIVE"
            if data_obj.get("customer"):
                org.billing_customer_id = str(data_obj["customer"])
            if data_obj.get("subscription"):
                org.billing_subscription_id = str(data_obj["subscription"])
        elif event_type == "customer.subscription.updated":
            sub_status = str(data_obj.get("status") or "").lower()
            if sub_status == "active":
                org.subscription_status = "ACTIVE"
            elif sub_status == "past_due":
                org.subscription_status = "PAST_DUE"
            elif sub_status in ("canceled", "unpaid"):
                org.subscription_status = "CANCELED"
        elif event_type == "customer.subscription.deleted":
            org.subscription_status = "CANCELED"
            apply_plan_quotas(org, "FREE")
        elif event_type == "invoice.payment_failed":
            org.subscription_status = "PAST_DUE"

        record_audit_event(
            db,
            action=f"billing.webhook.{event_type}",
            resource_type="organization",
            resource_id=org.id,
            organization_id=org.id,
            details={"external_event_id": event_id},
        )

    db.commit()
    return {"received": True, "duplicate": False}


@router.post("/v1/organization/suspend", response_model=OrganizationResponse)
def suspend_organization(
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_OWNER_ROLES)
    org.status = "SUSPENDED"
    org.updated_at = datetime.now(UTC)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.suspend",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@router.post("/v1/organization/unsuspend", response_model=OrganizationResponse)
def unsuspend_organization(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationResponse:
    """Allow an OWNER to reactivate a SUSPENDED organization."""
    if current_user.must_change_password:
        raise ProblemException(
            status_code=403,
            code="PASSWORD_CHANGE_REQUIRED",
            title="Password Change Required",
            detail="Must change temporary password first",
        )
    org, _ = _require_org_member(
        db, current_user, allowed_roles=ORG_OWNER_ROLES, allow_suspended=True
    )
    if org.status == "PENDING_DELETION":
        raise ProblemException(
            status_code=409,
            code="CONFLICT",
            title="Conflict",
            detail="Organization pending deletion cannot be unsuspended automatically",
        )
    org.status = "ACTIVE"
    org.updated_at = datetime.now(UTC)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.unsuspend",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@router.post("/v1/organization/delete", status_code=202)
def schedule_organization_deletion(
    payload: AccountDeleteRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_OWNER_ROLES)
    if payload.confirm_slug.strip() != org.slug:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="confirm_slug must match your organization slug",
        )
    now = datetime.now(UTC)
    org.status = "PENDING_DELETION"
    org.deleted_at = now
    org.updated_at = now

    org_users = list(db.scalars(select(User).where(User.organization_id == org.id)))
    for u in org_users:
        revoke_all_user_sessions(db, u, bump_token_version=True)

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.delete",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()
    return {"status": "PENDING_DELETION"}


@router.get("/v1/organization/export")
def export_organization_data(
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Export tenant projects, members, permits, site logs, and photo metadata safely."""
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_ADMIN_ROLES)
    projects = list(
        db.scalars(select(Project).where(Project.organization_id == org.id))
    )
    project_ids = [p.id for p in projects]
    members = list(db.scalars(select(User).where(User.organization_id == org.id)))
    permits = (
        list(db.scalars(select(Permit).where(Permit.project_id.in_(project_ids))))
        if project_ids
        else []
    )
    logs = (
        list(db.scalars(select(SiteLog).where(SiteLog.project_id.in_(project_ids))))
        if project_ids
        else []
    )
    log_ids = [item.id for item in logs]
    photos = (
        list(db.scalars(select(SiteLogPhoto).where(SiteLogPhoto.site_log_id.in_(log_ids))))
        if log_ids
        else []
    )

    ip_addr, user_agent = extract_client_meta(request)
    record_audit_event(
        db,
        action="organization.data_export",
        resource_type="organization",
        resource_id=org.id,
        actor_user=current_user,
        organization_id=org.id,
        ip_address=ip_addr,
        user_agent=user_agent,
    )
    db.commit()

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "organization": _serialize_org(org).model_dump(mode="json"),
        "members": [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
            }
            for u in members
        ],
        "projects": [
            {
                "id": str(p.id),
                "name": p.name,
                "site_address": p.site_address,
                "timezone": p.timezone,
                "deleted_at": p.deleted_at.isoformat() if p.deleted_at else None,
            }
            for p in projects
        ],
        "permits": [
            {
                "id": str(pm.id),
                "project_id": str(pm.project_id),
                "permit_name": pm.permit_name,
                "authority": pm.authority,
                "permit_number": pm.permit_number,
                "issue_date": pm.issue_date.isoformat() if pm.issue_date else None,
                "expiry_date": pm.expiry_date.isoformat(),
                "deleted_at": pm.deleted_at.isoformat() if pm.deleted_at else None,
            }
            for pm in permits
        ],
        "site_logs": [
            {
                "id": str(lg.id),
                "project_id": str(lg.project_id),
                "log_date": lg.log_date.isoformat(),
                "recorded_at": lg.recorded_at.isoformat(),
                "notes": lg.notes,
                "transcript": lg.transcript,
                "structured_summary": lg.structured_summary,
                "deleted_at": lg.deleted_at.isoformat() if lg.deleted_at else None,
            }
            for lg in logs
        ],
        "photos": [
            {
                "id": str(ph.id),
                "site_log_id": str(ph.site_log_id),
                "storage_uri": ph.storage_uri,
                "byte_size": ph.byte_size,
                "ai_caption": ph.ai_caption,
                "deleted_at": ph.deleted_at.isoformat() if ph.deleted_at else None,
            }
            for ph in photos
        ],
    }


@router.get("/v1/organization/audit-logs", response_model=AuditLogListResponse)
def list_organization_audit_logs(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=120)] = None,
) -> AuditLogListResponse:
    org, _ = _require_org_member(db, current_user, allowed_roles=ORG_AUDIT_VIEW_ROLES)
    base_filter = [AuditLog.organization_id == org.id]
    if action:
        base_filter.append(AuditLog.action == action.strip())

    total = int(
        db.scalar(select(func.count()).select_from(AuditLog).where(*base_filter)) or 0
    )
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(*base_filter)
            .order_by(AuditLog.sequence_num.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return AuditLogListResponse(
        items=[AuditLogItemResponse.model_validate(item) for item in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
