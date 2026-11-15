from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    Request,
    Response,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import (
    extract_client_meta,
    get_storage,
    get_verified_user,
    require_active_project_member,
)
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.permissions import (
    LOG_WRITE_ROLES,
    PERMIT_WRITE_ROLES,
    PROJECT_ELEVATED_RECORD_ROLES,
)
from app.core.rate_limit import rate_limiter
from app.db.models import (
    MediaReservation,
    Organization,
    Permit,
    SiteLog,
    SiteLogPhoto,
    UploadTicket,
    User,
)
from app.db.session import get_db
from app.schemas.media import (
    MediaCompleteRequest,
    MediaReservationRequest,
    MediaReservationResponse,
    UploadTicketResponse,
    UploadUrlRequest,
)
from app.services.audit import record_audit_event
from app.services.extraction_worker import enqueue_extraction_job, execute_extraction_job
from app.services.media_security import (
    MAX_UPLOAD_BYTES,
    compute_sha256_hex,
    resolve_extension_for_kind,
    sanitize_relative_object_key,
    validate_magic_bytes,
)
from app.services.saas import enforce_storage_quota, ensure_org_active
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1/media", tags=["media"])


def _can_access_record(member_role: str, owner_user_id: UUID, actor_user_id: UUID) -> bool:
    return member_role in PROJECT_ELEVATED_RECORD_ROLES or owner_user_id == actor_user_id


def _check_existing_record_for_media(
    db: Session,
    *,
    kind: str,
    project_id: UUID,
    object_id: UUID,
    member_role: str,
    actor_user_id: UUID,
) -> bool:
    """Validate ownership if the target record already exists. Return True if found."""
    if kind == "AUDIO":
        log = db.get(SiteLog, object_id)
        if log is not None:
            if log.project_id != project_id or log.deleted_at is not None:
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="Target site log does not belong to this project",
                )
            if not _can_access_record(member_role, log.author_id, actor_user_id):
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="You do not have permission to upload audio for this log",
                )
            if log.audio_upload_status == "UPLOADED":
                raise ProblemException(
                    status_code=409,
                    code="ALREADY_UPLOADED",
                    title="Conflict",
                    detail="Audio has already been uploaded for this log",
                )
            return True
    elif kind == "PHOTO":
        photo = db.get(SiteLogPhoto, object_id)
        if photo is not None:
            parent_log = db.get(SiteLog, photo.site_log_id)
            if (
                parent_log is None
                or parent_log.project_id != project_id
                or parent_log.deleted_at is not None
                or photo.deleted_at is not None
            ):
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="Target photo does not belong to this project",
                )
            if not _can_access_record(member_role, parent_log.author_id, actor_user_id):
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="You do not have permission to modify this site photo",
                )
            if photo.upload_status == "UPLOADED":
                raise ProblemException(
                    status_code=409,
                    code="ALREADY_UPLOADED",
                    title="Conflict",
                    detail="Site photo has already been uploaded cleanly",
                )
            return True
    elif kind == "PERMIT_DOC":
        permit = db.get(Permit, object_id)
        if permit is not None:
            if permit.project_id != project_id or permit.deleted_at is not None:
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="Target permit does not belong to this project",
                )
            if not _can_access_record(member_role, permit.created_by, actor_user_id):
                raise ProblemException(
                    status_code=403,
                    code="FORBIDDEN",
                    title="Forbidden",
                    detail="You do not have permission to replace this permit document",
                )
            return True
    return False


def _verify_target_ownership_for_ticket(
    db: Session,
    *,
    kind: str,
    project_id: UUID,
    object_id: UUID,
    member_role: str,
    actor_user_id: UUID,
) -> MediaReservation | None:
    record_exists = _check_existing_record_for_media(
        db,
        kind=kind,
        project_id=project_id,
        object_id=object_id,
        member_role=member_role,
        actor_user_id=actor_user_id,
    )

    reservation: MediaReservation | None = None
    if not record_exists:
        now = datetime.now(UTC)
        reservation = db.scalar(
            select(MediaReservation)
            .where(
                MediaReservation.kind == kind,
                MediaReservation.object_id == object_id,
            )
            .order_by(MediaReservation.created_at.desc())
            .with_for_update()
        )
        if reservation is None:
            raise ProblemException(
                status_code=409,
                code="RESERVATION_REQUIRED",
                title="Reservation Required",
                detail=(
                    "Target record does not exist; register a pending media reservation "
                    "or sync the record before requesting an upload URL"
                ),
            )
        if reservation.project_id != project_id or reservation.user_id != actor_user_id:
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Target media reservation belongs to another user or project",
            )
        if reservation.status == "ACTIVE" and reservation.expires_at <= now:
            reservation.status = "EXPIRED"
            db.commit()
            raise ProblemException(
                status_code=403,
                code="RESERVATION_EXPIRED",
                title="Reservation Expired",
                detail="Media reservation has expired; register a new reservation",
            )
        if reservation.status == "EXPIRED":
            raise ProblemException(
                status_code=403,
                code="RESERVATION_EXPIRED",
                title="Reservation Expired",
                detail="Media reservation has expired; register a new reservation",
            )
        if reservation.status != "ACTIVE":
            raise ProblemException(
                status_code=409,
                code="RESERVATION_REQUIRED",
                title="Reservation Required",
                detail="No active media reservation exists for this target object",
            )

    # Also block another user from issuing a ticket for an object_id already claimed by someone else
    other_ticket = db.scalar(
        select(UploadTicket).where(
            UploadTicket.kind == kind,
            UploadTicket.object_id == object_id,
            UploadTicket.user_id != actor_user_id,
            UploadTicket.status.in_(("ISSUED", "UPLOADED", "COMPLETED")),
        )
    )
    if other_ticket is not None and (
        not record_exists or member_role not in PROJECT_ELEVATED_RECORD_ROLES
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Target media object is bound to another user",
        )
    return reservation


@router.post(
    "/reservations",
    response_model=MediaReservationResponse,
    status_code=201,
)
def create_media_reservation(
    payload: MediaReservationRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaReservationResponse:
    """Reserve an offline-generated target object_id bound to user, project, and org."""
    limit_decision = rate_limiter.check(
        f"media-reserve:user:{current_user.id}",
        settings.RATE_LIMIT_MEDIA_UPLOADS_PER_MINUTE,
        60,
    )
    if not limit_decision.allowed:
        raise ProblemException(
            status_code=429,
            code="RATE_LIMITED",
            title="Too Many Requests",
            detail="Too many media reservation requests; try again shortly.",
            headers={"Retry-After": str(limit_decision.retry_after_seconds)},
        )

    ip_addr, user_agent = extract_client_meta(request)
    allowed_roles = (
        PERMIT_WRITE_ROLES if payload.kind == "PERMIT_DOC" else LOG_WRITE_ROLES
    )
    project, member = require_active_project_member(
        db,
        payload.project_id,
        current_user,
        allowed_roles=allowed_roles,
    )

    _check_existing_record_for_media(
        db,
        kind=payload.kind,
        project_id=project.id,
        object_id=payload.object_id,
        member_role=member.role,
        actor_user_id=current_user.id,
    )

    now = datetime.now(UTC)
    ttl_seconds = payload.ttl_seconds or settings.MEDIA_RESERVATION_TTL_SECONDS
    desired_expires_at = now + timedelta(seconds=ttl_seconds)

    existing_active = db.scalar(
        select(MediaReservation)
        .where(
            MediaReservation.kind == payload.kind,
            MediaReservation.object_id == payload.object_id,
            MediaReservation.status == "ACTIVE",
        )
        .with_for_update()
    )
    if existing_active is not None:
        if existing_active.expires_at <= now:
            existing_active.status = "EXPIRED"
            db.flush()
        elif (
            existing_active.user_id != current_user.id
            or existing_active.project_id != project.id
        ):
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="Target object identifier is already reserved by another user or project",
            )
        else:
            existing_active.expires_at = max(existing_active.expires_at, desired_expires_at)
            db.commit()
            db.refresh(existing_active)
            return MediaReservationResponse(
                reservation_id=existing_active.id,
                kind=payload.kind,
                project_id=existing_active.project_id,
                object_id=existing_active.object_id,
                status="ACTIVE",
                expires_at=existing_active.expires_at,
            )

    reservation = MediaReservation(
        organization_id=project.organization_id,
        project_id=project.id,
        user_id=current_user.id,
        kind=payload.kind,
        object_id=payload.object_id,
        status="ACTIVE",
        expires_at=desired_expires_at,
    )
    db.add(reservation)
    db.flush()

    record_audit_event(
        db,
        action="media.reservation_created",
        resource_type="media_reservation",
        resource_id=reservation.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={
            "kind": payload.kind,
            "project_id": str(project.id),
            "object_id": str(payload.object_id),
        },
    )
    db.commit()
    db.refresh(reservation)
    return MediaReservationResponse(
        reservation_id=reservation.id,
        kind=payload.kind,
        project_id=reservation.project_id,
        object_id=reservation.object_id,
        status="ACTIVE",
        expires_at=reservation.expires_at,
    )


@router.post("/upload-url", response_model=UploadTicketResponse)
def create_upload_url(
    payload: UploadUrlRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UploadTicketResponse:
    limit_decision = rate_limiter.check(
        f"media-upload-url:user:{current_user.id}",
        settings.RATE_LIMIT_MEDIA_UPLOADS_PER_MINUTE,
        60,
    )
    if not limit_decision.allowed:
        raise ProblemException(
            status_code=429,
            code="RATE_LIMITED",
            title="Too Many Requests",
            detail="Upload ticket rate limit exceeded; try again shortly.",
            headers={"Retry-After": str(limit_decision.retry_after_seconds)},
        )

    ip_addr, user_agent = extract_client_meta(request)

    if resolve_extension_for_kind(payload.kind, payload.content_type) is None:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail=f"Unsupported content_type '{payload.content_type}' for kind {payload.kind}",
        )

    allowed_roles = (
        PERMIT_WRITE_ROLES if payload.kind == "PERMIT_DOC" else LOG_WRITE_ROLES
    )
    project, member = require_active_project_member(
        db,
        payload.project_id,
        current_user,
        allowed_roles=allowed_roles,
    )

    reservation = _verify_target_ownership_for_ticket(
        db,
        kind=payload.kind,
        project_id=project.id,
        object_id=payload.object_id,
        member_role=member.role,
        actor_user_id=current_user.id,
    )

    now = datetime.now(UTC)

    # Revoke prior un-uploaded ISSUED tickets for this user/object before quota check & re-issue
    prior_tickets = list(
        db.scalars(
            select(UploadTicket)
            .where(
                UploadTicket.project_id == project.id,
                UploadTicket.kind == payload.kind,
                UploadTicket.object_id == payload.object_id,
                UploadTicket.user_id == current_user.id,
                UploadTicket.status == "ISSUED",
            )
            .with_for_update()
        )
    )
    for old_t in prior_tickets:
        old_t.status = "REVOKED"
    db.flush()

    if project.organization_id is not None:
        org = db.scalar(
            select(Organization)
            .where(Organization.id == project.organization_id)
            .with_for_update()
        )
        if org is not None:
            ensure_org_active(org)
            in_flight_bytes = int(
                db.scalar(
                    select(func.coalesce(func.sum(UploadTicket.expected_byte_size), 0)).where(
                        UploadTicket.organization_id == org.id,
                        UploadTicket.status.in_(("ISSUED", "UPLOADED")),
                        UploadTicket.expires_at > now,
                    )
                )
                or 0
            )
            enforce_storage_quota(org, in_flight_bytes + payload.byte_size)

    ticket_id = uuid4()
    ticket = storage.create_upload_ticket(
        project_id=payload.project_id,
        kind=payload.kind,
        object_id=payload.object_id,
        content_type=payload.content_type,
        ticket_id=ticket_id,
        expected_byte_size=payload.byte_size,
    )
    expires_at = now + timedelta(seconds=settings.SIGNED_URL_TTL_SECONDS)

    db.add(
        UploadTicket(
            id=ticket_id,
            organization_id=project.organization_id,
            project_id=project.id,
            user_id=current_user.id,
            kind=payload.kind,
            object_id=payload.object_id,
            object_key=ticket.object_key,
            storage_uri=ticket.storage_uri,
            content_type=payload.content_type,
            expected_byte_size=payload.byte_size,
            reservation_id=reservation.id if reservation is not None else None,
            status="ISSUED",
            expires_at=expires_at,
        )
    )
    record_audit_event(
        db,
        action="media.upload_ticket_issued",
        resource_type=payload.kind.lower(),
        resource_id=payload.object_id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={
            "ticket_id": str(ticket_id),
            "project_id": str(project.id),
            "content_type": payload.content_type,
            "byte_size": payload.byte_size,
        },
    )
    db.commit()

    return UploadTicketResponse(
        ticket_id=ticket_id,
        upload_url=ticket.upload_url,
        headers=ticket.headers,
        storage_uri=ticket.storage_uri,
        expires_at=ticket.expires_at,
    )


def _find_completable_ticket(
    db: Session,
    *,
    payload: MediaCompleteRequest,
    project_id: UUID,
    actor_user_id: UUID,
    storage_uri: str | None,
) -> UploadTicket | None:
    if payload.ticket_id is not None:
        return db.scalar(
            select(UploadTicket)
            .where(UploadTicket.id == payload.ticket_id)
            .with_for_update()
        )
    stmt = (
        select(UploadTicket)
        .where(
            UploadTicket.project_id == project_id,
            UploadTicket.kind == payload.kind,
            UploadTicket.object_id == payload.object_id,
            UploadTicket.user_id == actor_user_id,
        )
        .order_by(UploadTicket.created_at.desc())
        .with_for_update()
    )
    if storage_uri:
        matching = db.scalar(stmt.where(UploadTicket.storage_uri == storage_uri))
        if matching is not None:
            return matching
    return db.scalar(stmt)


def _validate_and_consume_ticket(
    db: Session,
    *,
    ticket: UploadTicket | None,
    payload: MediaCompleteRequest,
    project_id: UUID,
    actor_user_id: UUID,
    storage: MediaStorageService,
) -> UploadTicket:
    if ticket is None:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="No valid upload ticket found for this object and user",
        )
    if ticket.user_id != actor_user_id:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Upload ticket belongs to a different user",
        )
    if (
        ticket.project_id != project_id
        or ticket.kind != payload.kind
        or ticket.object_id != payload.object_id
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Upload ticket does not match target project or record",
        )
    if ticket.status == "COMPLETED":
        raise ProblemException(
            status_code=409,
            code="TICKET_ALREADY_COMPLETED",
            title="Conflict",
            detail="Upload ticket has already been completed",
        )
    if ticket.status in ("EXPIRED", "REVOKED"):
        raise ProblemException(
            status_code=403,
            code="TICKET_EXPIRED",
            title="Forbidden",
            detail="Upload ticket is expired or revoked",
        )
    now = datetime.now(UTC)
    if ticket.expires_at <= now:
        ticket.status = "EXPIRED"
        db.commit()
        raise ProblemException(
            status_code=403,
            code="TICKET_EXPIRED",
            title="Forbidden",
            detail="Upload ticket has expired",
        )

    info = storage.inspect_object(ticket.storage_uri)
    if not info.exists:
        raise ProblemException(
            status_code=404,
            code="OBJECT_MISSING",
            title="Object Missing",
            detail="Media file has not been uploaded to storage yet",
        )
    if info.byte_size != ticket.expected_byte_size:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Uploaded file size does not match authorized upload ticket",
        )
    if not validate_magic_bytes(ticket.content_type, info.header_bytes):
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Uploaded file contents do not match declared MIME type",
        )
    if payload.sha256 is not None:
        raw_bytes = storage.read_bytes(ticket.storage_uri, max_bytes=20_971_520)
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        if actual_sha256.lower() != payload.sha256.lower():
            raise ProblemException(
                status_code=422,
                code="VALIDATION",
                title="Validation Error",
                detail="Uploaded file SHA-256 checksum does not match expected digest",
            )

    ticket.actual_byte_size = info.byte_size
    ticket.status = "COMPLETED"
    ticket.completed_at = now
    return ticket


def _finalize_upload_org_and_reservation(
    db: Session,
    *,
    organization_id: UUID | None,
    kind: str,
    object_id: UUID,
    actual_byte_size: int | None,
) -> None:
    """Update organization storage usage and consume any pending reservation."""
    if organization_id is not None:
        org = db.scalar(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
        )
        if org is not None:
            org.storage_bytes_used = int(org.storage_bytes_used or 0) + (
                actual_byte_size or 0
            )
    active_res = db.scalar(
        select(MediaReservation)
        .where(
            MediaReservation.kind == kind,
            MediaReservation.object_id == object_id,
            MediaReservation.status == "ACTIVE",
        )
        .with_for_update()
    )
    if active_res is not None:
        active_res.status = "CONSUMED"
        active_res.consumed_at = datetime.now(UTC)


@router.post("/complete", status_code=204)
def complete_media_upload(
    payload: MediaCompleteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    ip_addr, user_agent = extract_client_meta(request)

    session_factory = sessionmaker(
        bind=db.get_bind(),
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    if payload.kind == "AUDIO":
        log = db.scalar(
            select(SiteLog).where(SiteLog.id == payload.object_id).with_for_update()
        )
        if log is None or log.deleted_at is not None:
            raise ProblemException(
                status_code=409,
                code="ROW_NOT_SYNCED",
                title="Row Not Synced",
                detail="Site log must be synced via /v1/sync/push before completing audio upload",
            )
        project, member = require_active_project_member(
            db, log.project_id, current_user, allowed_roles=LOG_WRITE_ROLES
        )
        if not _can_access_record(member.role, log.author_id, current_user.id):
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="You cannot complete media upload for another user's log",
            )

        ticket = _find_completable_ticket(
            db,
            payload=payload,
            project_id=log.project_id,
            actor_user_id=current_user.id,
            storage_uri=log.audio_uri,
        )
        consumed = _validate_and_consume_ticket(
            db,
            ticket=ticket,
            payload=payload,
            project_id=log.project_id,
            actor_user_id=current_user.id,
            storage=storage,
        )
        log.audio_uri = consumed.storage_uri
        log.audio_upload_status = "UPLOADED"
        log.extraction_status = "PENDING"
        log.extraction_error = None
        _finalize_upload_org_and_reservation(
            db,
            organization_id=project.organization_id,
            kind="AUDIO",
            object_id=log.id,
            actual_byte_size=consumed.actual_byte_size,
        )

        job, should_run_local = enqueue_extraction_job(
            db,
            organization_id=project.organization_id,
            project_id=log.project_id,
            target_type="SITE_LOG",
            target_id=log.id,
            idempotency_key=f"SITE_LOG:{log.id}:{consumed.id}",
            settings=settings,
            force_reset=True,
        )
        record_audit_event(
            db,
            action="media.completed",
            resource_type="site_log",
            resource_id=log.id,
            actor_user=current_user,
            organization_id=project.organization_id,
            ip_address=ip_addr,
            user_agent=user_agent,
            details={"kind": "AUDIO", "ticket_id": str(consumed.id)},
        )
        db.commit()

        if should_run_local:
            background_tasks.add_task(
                execute_extraction_job,
                job.id,
                session_factory,
                settings,
            )
        return Response(status_code=204)

    if payload.kind == "PHOTO":
        row = db.execute(
            select(SiteLogPhoto, SiteLog)
            .join(SiteLog, SiteLog.id == SiteLogPhoto.site_log_id)
            .where(
                SiteLogPhoto.id == payload.object_id,
                SiteLogPhoto.deleted_at.is_(None),
                SiteLog.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            raise ProblemException(
                status_code=409,
                code="ROW_NOT_SYNCED",
                title="Row Not Synced",
                detail="Site log photo must be synced via /v1/sync/push before completing upload",
            )
        photo, parent_log = row[0], row[1]
        project, member = require_active_project_member(
            db, parent_log.project_id, current_user, allowed_roles=LOG_WRITE_ROLES
        )
        if not _can_access_record(member.role, parent_log.author_id, current_user.id):
            raise ProblemException(
                status_code=403,
                code="FORBIDDEN",
                title="Forbidden",
                detail="You cannot complete photo upload for another user's log",
            )

        ticket = _find_completable_ticket(
            db,
            payload=payload,
            project_id=parent_log.project_id,
            actor_user_id=current_user.id,
            storage_uri=photo.storage_uri,
        )
        consumed = _validate_and_consume_ticket(
            db,
            ticket=ticket,
            payload=payload,
            project_id=parent_log.project_id,
            actor_user_id=current_user.id,
            storage=storage,
        )
        photo.storage_uri = consumed.storage_uri
        photo.upload_status = "UPLOADED"
        photo.byte_size = consumed.actual_byte_size
        _finalize_upload_org_and_reservation(
            db,
            organization_id=project.organization_id,
            kind="PHOTO",
            object_id=photo.id,
            actual_byte_size=consumed.actual_byte_size,
        )

        job, should_run_local = enqueue_extraction_job(
            db,
            organization_id=project.organization_id,
            project_id=parent_log.project_id,
            target_type="SITE_LOG_PHOTO",
            target_id=photo.id,
            idempotency_key=f"SITE_LOG_PHOTO:{photo.id}:{consumed.id}",
            settings=settings,
        )
        record_audit_event(
            db,
            action="media.completed",
            resource_type="site_log_photo",
            resource_id=photo.id,
            actor_user=current_user,
            organization_id=project.organization_id,
            ip_address=ip_addr,
            user_agent=user_agent,
            details={"kind": "PHOTO", "ticket_id": str(consumed.id)},
        )
        db.commit()

        if should_run_local:
            background_tasks.add_task(
                execute_extraction_job,
                job.id,
                session_factory,
                settings,
            )
        return Response(status_code=204)

    # PERMIT_DOC
    permit = db.scalar(
        select(Permit).where(Permit.id == payload.object_id).with_for_update()
    )
    if permit is None or permit.deleted_at is not None:
        raise ProblemException(
            status_code=409,
            code="ROW_NOT_SYNCED",
            title="Row Not Synced",
            detail="Permit must be synced or created before completing document upload",
        )
    project, member = require_active_project_member(
        db, permit.project_id, current_user, allowed_roles=PERMIT_WRITE_ROLES
    )
    if not _can_access_record(member.role, permit.created_by, current_user.id):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="You cannot complete document upload for another user's permit",
        )

    ticket = _find_completable_ticket(
        db,
        payload=payload,
        project_id=permit.project_id,
        actor_user_id=current_user.id,
        storage_uri=permit.document_photo_uri,
    )
    consumed = _validate_and_consume_ticket(
        db,
        ticket=ticket,
        payload=payload,
        project_id=permit.project_id,
        actor_user_id=current_user.id,
        storage=storage,
    )
    permit.document_photo_uri = consumed.storage_uri
    permit.document_upload_status = "UPLOADED"
    _finalize_upload_org_and_reservation(
        db,
        organization_id=project.organization_id,
        kind="PERMIT_DOC",
        object_id=permit.id,
        actual_byte_size=consumed.actual_byte_size,
    )

    job, should_run_local = enqueue_extraction_job(
        db,
        organization_id=project.organization_id,
        project_id=permit.project_id,
        target_type="PERMIT",
        target_id=permit.id,
        idempotency_key=f"PERMIT:{permit.id}:{consumed.id}",
        settings=settings,
        force_reset=True,
    )
    record_audit_event(
        db,
        action="media.completed",
        resource_type="permit",
        resource_id=permit.id,
        actor_user=current_user,
        organization_id=project.organization_id,
        ip_address=ip_addr,
        user_agent=user_agent,
        details={"kind": "PERMIT_DOC", "ticket_id": str(consumed.id)},
    )
    db.commit()

    if should_run_local:
        background_tasks.add_task(
            execute_extraction_job,
            job.id,
            session_factory,
            settings,
        )
    return Response(status_code=204)


@router.put("/local/{object_key:path}", status_code=200)
async def put_local_media(
    object_key: str,
    request: Request,
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    ticket: Annotated[str, Query()] = "",
) -> dict[str, str]:
    clean_key = sanitize_relative_object_key(object_key)
    if clean_key is None:
        raise ProblemException(
            status_code=400,
            code="VALIDATION",
            title="Validation Error",
            detail="Invalid object key path",
        )
    if storage.backend != "local":
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Local media route is disabled when STORAGE_BACKEND != local",
        )
    if not ticket:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Missing upload ticket identifier",
        )
    try:
        ticket_uuid = UUID(ticket)
    except ValueError as exc:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Malformed upload ticket identifier",
        ) from exc

    if not storage.verify_local_signature("PUT", clean_key, exp, sig, ticket_id=ticket):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid or expired local upload signature",
        )

    ticket_row = db.scalar(
        select(UploadTicket).where(UploadTicket.id == ticket_uuid).with_for_update()
    )
    if ticket_row is None or ticket_row.object_key != clean_key:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Upload ticket does not match target object",
        )
    now = datetime.now(UTC)
    if ticket_row.expires_at <= now:
        ticket_row.status = "EXPIRED"
        db.commit()
        raise ProblemException(
            status_code=403,
            code="TICKET_EXPIRED",
            title="Forbidden",
            detail="Upload ticket expired",
        )
    if ticket_row.status != "ISSUED":
        raise ProblemException(
            status_code=409,
            code="OBJECT_EXISTS",
            title="Conflict",
            detail="Upload ticket already used; overwriting media objects is forbidden",
        )

    req_ct = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if req_ct and req_ct != ticket_row.content_type.lower():
        raise ProblemException(
            status_code=415,
            code="UNSUPPORTED_MEDIA_TYPE",
            title="Unsupported Media Type",
            detail="Request Content-Type does not match upload ticket",
        )

    # Stream body incrementally to prevent memory exhaustion on oversized uploads
    max_allowed = min(int(ticket_row.expected_byte_size), MAX_UPLOAD_BYTES)
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise ProblemException(
                status_code=413,
                code="BATCH_TOO_LARGE",
                title="Payload Too Large",
                detail=f"File exceeds {MAX_UPLOAD_BYTES} byte upload limit",
            )
        if total_bytes > max_allowed:
            raise ProblemException(
                status_code=422,
                code="VALIDATION",
                title="Validation Error",
                detail="Uploaded payload exceeds ticket byte_size",
            )
        chunks.append(chunk)

    body = b"".join(chunks)
    if not body or len(body) != int(ticket_row.expected_byte_size):
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="Uploaded byte length does not match expected ticket byte_size",
        )

    if not validate_magic_bytes(ticket_row.content_type, body[:128]):
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail="File content signature does not match declared MIME type",
        )

    try:
        storage.write_local_bytes_exclusive(clean_key, body)
    except FileExistsError as exc:
        raise ProblemException(
            status_code=409,
            code="OBJECT_EXISTS",
            title="Conflict",
            detail="Target media object already exists and cannot be overwritten",
        ) from exc

    ticket_row.status = "UPLOADED"
    ticket_row.actual_byte_size = len(body)
    ticket_row.sha256 = compute_sha256_hex(body)
    ticket_row.uploaded_at = now
    db.commit()
    return {"status": "uploaded", "storage_uri": ticket_row.storage_uri}


@router.get("/local/{object_key:path}")
def get_local_media(
    object_key: str,
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query()],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> FileResponse:
    clean_key = sanitize_relative_object_key(object_key)
    if clean_key is None:
        raise ProblemException(
            status_code=400,
            code="VALIDATION",
            title="Validation Error",
            detail="Invalid object key",
        )
    if storage.backend != "local":
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Local media route is disabled when STORAGE_BACKEND != local",
        )
    if not storage.verify_local_signature("GET", clean_key, exp, sig):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid or expired media URL",
        )
    try:
        path = storage.safe_local_path(clean_key)
    except ValueError as exc:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Forbidden media path",
        ) from exc
    if not path.is_file():
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Media file not found",
        )
    guessed_type, _ = mimetypes.guess_type(path.name)
    safe_headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'attachment; filename="{path.name}"',
        "Cache-Control": "private, max-age=300",
    }
    return FileResponse(
        path,
        media_type=guessed_type or "application/octet-stream",
        headers=safe_headers,
    )
