from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import BigInteger, String, literal, select, text, union_all, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_storage, get_verified_user
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.logging_config import safe_public_error_summary
from app.core.permissions import (
    LOG_WRITE_ROLES,
    PERMIT_WRITE_ROLES,
    PROJECT_ELEVATED_RECORD_ROLES,
    Role,
)
from app.db.models import (
    Organization,
    Permit,
    PermitWithStatus,
    Project,
    ProjectMember,
    SiteLog,
    SiteLogPhoto,
    UploadTicket,
    User,
)
from app.db.session import get_db
from app.schemas.projects import MemberResponse, ProjectResponse
from app.schemas.sync import (
    PermitPush,
    SiteLogPhotoPush,
    SiteLogPush,
    SyncPullChanges,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncPushResultItem,
)
from app.services.media_security import validate_project_storage_uri
from app.services.reports import (
    serialize_permit,
    serialize_photo,
    serialize_site_log_pull,
)
from app.services.saas import ensure_org_active
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1/sync", tags=["sync"])

MAX_PUSH_RECORDS = 200
_ZERO_UUID = UUID(int=0)


def _extract_raw_uuid(raw: dict[str, Any]) -> UUID:
    val = raw.get("id")
    if isinstance(val, UUID):
        return val
    if isinstance(val, str):
        try:
            return UUID(val)
        except ValueError:
            return _ZERO_UUID
    return _ZERO_UUID


def _resolve_active_member_for_push(
    db: Session,
    *,
    entity: Literal["permits", "site_logs", "site_log_photos"],
    record_id: UUID,
    project_id: UUID,
    current_user: User,
    project_cache: dict[UUID, Project | None],
    member_cache: dict[UUID, ProjectMember | None],
    allowed_roles: frozenset[str],
) -> ProjectMember | SyncPushResultItem:
    if project_id not in project_cache:
        project_cache[project_id] = db.get(Project, project_id)
    project = project_cache[project_id]

    if project is None:
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="NOT_FOUND",
            error_detail="Project not found",
        )
    if (
        current_user.organization_id is not None
        and project.organization_id is not None
        and project.organization_id != current_user.organization_id
    ):
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="NOT_FOUND",
            error_detail="Project not found",
        )
    if project.deleted_at is not None:
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="PROJECT_DELETED",
            error_detail="Project has been deleted",
        )
    if project.organization_id is not None:
        org = db.get(Organization, project.organization_id)
        try:
            ensure_org_active(org)
        except ProblemException as exc:
            return SyncPushResultItem(
                entity=entity,
                id=record_id,
                status="REJECTED",
                error_code=exc.code,
                error_detail=exc.detail,
            )

    if project_id not in member_cache:
        member_cache[project_id] = db.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
        )
    member = member_cache[project_id]
    if member is None:
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="FORBIDDEN",
            error_detail="Active project membership required",
        )
    if member.role not in allowed_roles:
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="FORBIDDEN",
            error_detail=f"Role {member.role} cannot push {entity}",
        )
    return member


def _has_uploaded_ticket(db: Session, project_id: UUID, storage_uri: str | None) -> bool:
    if not storage_uri:
        return False
    row = db.scalar(
        select(UploadTicket.id).where(
            UploadTicket.project_id == project_id,
            UploadTicket.storage_uri == storage_uri,
            UploadTicket.status.in_(("UPLOADED", "COMPLETED")),
        )
    )
    return row is not None


def _apply_permit_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
    *,
    settings: Settings,
    project_cache: dict[UUID, Project | None],
    member_cache: dict[UUID, ProjectMember | None],
) -> SyncPushResultItem:
    raw_id = _extract_raw_uuid(raw)
    try:
        item = PermitPush.model_validate(raw)
    except ValidationError as exc:
        return SyncPushResultItem(
            entity="permits",
            id=raw_id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Invalid permit payload"),
        )

    uri_ok, uri_err = validate_project_storage_uri(
        item.document_photo_uri,
        project_id=item.project_id,
        storage_backend=settings.STORAGE_BACKEND,
        gcs_bucket=settings.GCS_BUCKET,
        expected_subdir="permits",
    )
    if not uri_ok:
        return SyncPushResultItem(
            entity="permits",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=uri_err or "Invalid document storage URI",
        )

    try:
        with db.begin_nested():
            member_or_err = _resolve_active_member_for_push(
                db,
                entity="permits",
                record_id=item.id,
                project_id=item.project_id,
                current_user=current_user,
                project_cache=project_cache,
                member_cache=member_cache,
                allowed_roles=PERMIT_WRITE_ROLES,
            )
            if isinstance(member_or_err, SyncPushResultItem):
                return member_or_err
            member = member_or_err

            existing = db.get(Permit, item.id)
            doc_status = (
                "NONE"
                if item.document_photo_uri is None
                else (
                    "UPLOADED"
                    if _has_uploaded_ticket(db, item.project_id, item.document_photo_uri)
                    else "PENDING"
                )
            )
            if existing is not None:
                if existing.project_id != item.project_id:
                    return SyncPushResultItem(
                        entity="permits",
                        id=item.id,
                        status="REJECTED",
                        error_code="FORBIDDEN",
                        error_detail="Cannot move permit to another project",
                    )
                if (
                    member.role not in PROJECT_ELEVATED_RECORD_ROLES
                    and existing.created_by != current_user.id
                ):
                    return SyncPushResultItem(
                        entity="permits",
                        id=item.id,
                        status="REJECTED",
                        error_code="FORBIDDEN",
                        error_detail="Insufficient permissions to modify this permit",
                    )
                if (
                    existing.client_updated_at is not None
                    and item.client_updated_at < existing.client_updated_at
                ):
                    return SyncPushResultItem(
                        entity="permits",
                        id=item.id,
                        status="REJECTED",
                        error_code="CONFLICT",
                        error_detail="Stale update rejected; newer version exists on server",
                    )
                server_version = db.scalar(
                    update(Permit)
                    .where(Permit.id == item.id)
                    .values(
                        permit_name=item.permit_name,
                        authority=item.authority,
                        permit_number=item.permit_number,
                        issue_date=item.issue_date,
                        expiry_date=item.expiry_date,
                        document_photo_uri=item.document_photo_uri,
                        document_upload_status=(
                            existing.document_upload_status
                            if existing.document_photo_uri == item.document_photo_uri
                            and existing.document_upload_status == "UPLOADED"
                            else doc_status
                        ),
                        deleted_at=item.deleted_at,
                        client_updated_at=item.client_updated_at,
                    )
                    .returning(Permit.server_version)
                )
            else:
                server_version = db.scalar(
                    pg_insert(Permit)
                    .values(
                        id=item.id,
                        project_id=item.project_id,
                        permit_name=item.permit_name,
                        authority=item.authority,
                        permit_number=item.permit_number,
                        issue_date=item.issue_date,
                        expiry_date=item.expiry_date,
                        document_photo_uri=item.document_photo_uri,
                        document_upload_status=doc_status,
                        created_by=current_user.id,
                        client_updated_at=item.client_updated_at,
                        deleted_at=item.deleted_at,
                    )
                    .returning(Permit.server_version)
                )

        return SyncPushResultItem(
            entity="permits",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        return SyncPushResultItem(
            entity="permits",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Permit sync rejected"),
        )


def _apply_site_log_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
    *,
    settings: Settings,
    project_cache: dict[UUID, Project | None],
    member_cache: dict[UUID, ProjectMember | None],
) -> SyncPushResultItem:
    raw_id = _extract_raw_uuid(raw)
    try:
        item = SiteLogPush.model_validate(raw)
    except ValidationError as exc:
        return SyncPushResultItem(
            entity="site_logs",
            id=raw_id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Invalid site log payload"),
        )

    uri_ok, uri_err = validate_project_storage_uri(
        item.audio_uri,
        project_id=item.project_id,
        storage_backend=settings.STORAGE_BACKEND,
        gcs_bucket=settings.GCS_BUCKET,
        expected_subdir="audio",
    )
    if not uri_ok:
        return SyncPushResultItem(
            entity="site_logs",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=uri_err or "Invalid audio storage URI",
        )

    try:
        with db.begin_nested():
            member_or_err = _resolve_active_member_for_push(
                db,
                entity="site_logs",
                record_id=item.id,
                project_id=item.project_id,
                current_user=current_user,
                project_cache=project_cache,
                member_cache=member_cache,
                allowed_roles=LOG_WRITE_ROLES,
            )
            if isinstance(member_or_err, SyncPushResultItem):
                return member_or_err
            member = member_or_err

            existing = db.get(SiteLog, item.id)
            if existing is not None:
                if existing.project_id != item.project_id:
                    return SyncPushResultItem(
                        entity="site_logs",
                        id=item.id,
                        status="REJECTED",
                        error_code="FORBIDDEN",
                        error_detail="Cannot move site log to another project",
                    )
                if (
                    member.role not in PROJECT_ELEVATED_RECORD_ROLES
                    and existing.author_id != current_user.id
                ):
                    return SyncPushResultItem(
                        entity="site_logs",
                        id=item.id,
                        status="REJECTED",
                        error_code="FORBIDDEN",
                        error_detail="Insufficient permissions to modify this site log",
                    )
                if item.client_updated_at < existing.client_updated_at:
                    return SyncPushResultItem(
                        entity="site_logs",
                        id=item.id,
                        status="REJECTED",
                        error_code="CONFLICT",
                        error_detail="Stale update rejected; newer version exists on server",
                    )
                # Tombstone precedence: do not silently undelete a deleted log via older edits
                if existing.deleted_at is not None and item.deleted_at is None:
                    return SyncPushResultItem(
                        entity="site_logs",
                        id=item.id,
                        status="REJECTED",
                        error_code="CONFLICT",
                        error_detail="Site log was deleted on server",
                    )

                if item.audio_uri is None:
                    next_audio_status = "NONE"
                elif (
                    existing.audio_uri == item.audio_uri
                    and existing.audio_upload_status == "UPLOADED"
                ) or _has_uploaded_ticket(db, item.project_id, item.audio_uri):
                    next_audio_status = "UPLOADED"
                else:
                    next_audio_status = "PENDING"

                update_values: dict[str, Any] = {
                    "log_date": item.log_date,
                    "recorded_at": item.recorded_at,
                    "notes": item.notes,
                    "audio_uri": item.audio_uri,
                    "audio_duration_ms": item.audio_duration_ms,
                    "audio_upload_status": next_audio_status,
                    "deleted_at": item.deleted_at,
                    "client_updated_at": item.client_updated_at,
                }
                if item.edited_by_human:
                    update_values["edited_by_human"] = True
                    if item.structured_summary is not None:
                        update_values["structured_summary"] = item.structured_summary.model_dump()

                server_version = db.scalar(
                    update(SiteLog)
                    .where(SiteLog.id == item.id)
                    .values(**update_values)
                    .returning(SiteLog.server_version)
                )
            else:
                initial_audio_status = (
                    "NONE"
                    if item.audio_uri is None
                    else (
                        "UPLOADED"
                        if _has_uploaded_ticket(db, item.project_id, item.audio_uri)
                        else "PENDING"
                    )
                )
                initial_summary = (
                    item.structured_summary.model_dump()
                    if item.edited_by_human and item.structured_summary is not None
                    else None
                )
                server_version = db.scalar(
                    pg_insert(SiteLog)
                    .values(
                        id=item.id,
                        project_id=item.project_id,
                        author_id=current_user.id,
                        log_date=item.log_date,
                        recorded_at=item.recorded_at,
                        notes=item.notes,
                        audio_uri=item.audio_uri,
                        audio_duration_ms=item.audio_duration_ms,
                        audio_upload_status=initial_audio_status,
                        structured_summary=initial_summary,
                        edited_by_human=bool(item.edited_by_human),
                        client_updated_at=item.client_updated_at,
                        deleted_at=item.deleted_at,
                    )
                    .returning(SiteLog.server_version)
                )

        return SyncPushResultItem(
            entity="site_logs",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        return SyncPushResultItem(
            entity="site_logs",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Site log sync rejected"),
        )


def _apply_photo_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
    *,
    settings: Settings,
    project_cache: dict[UUID, Project | None],
    member_cache: dict[UUID, ProjectMember | None],
) -> SyncPushResultItem:
    raw_id = _extract_raw_uuid(raw)
    try:
        item = SiteLogPhotoPush.model_validate(raw)
    except ValidationError as exc:
        return SyncPushResultItem(
            entity="site_log_photos",
            id=raw_id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Invalid photo payload"),
        )

    try:
        with db.begin_nested():
            parent_log = db.get(SiteLog, item.site_log_id)
            if parent_log is None or parent_log.deleted_at is not None:
                return SyncPushResultItem(
                    entity="site_log_photos",
                    id=item.id,
                    status="REJECTED",
                    error_code="NOT_FOUND",
                    error_detail="Parent site_log not found or deleted",
                )

            uri_ok, uri_err = validate_project_storage_uri(
                item.storage_uri,
                project_id=parent_log.project_id,
                storage_backend=settings.STORAGE_BACKEND,
                gcs_bucket=settings.GCS_BUCKET,
                expected_subdir="photos",
            )
            if not uri_ok:
                return SyncPushResultItem(
                    entity="site_log_photos",
                    id=item.id,
                    status="REJECTED",
                    error_code="VALIDATION",
                    error_detail=uri_err or "Invalid photo storage URI",
                )

            member_or_err = _resolve_active_member_for_push(
                db,
                entity="site_log_photos",
                record_id=item.id,
                project_id=parent_log.project_id,
                current_user=current_user,
                project_cache=project_cache,
                member_cache=member_cache,
                allowed_roles=LOG_WRITE_ROLES,
            )
            if isinstance(member_or_err, SyncPushResultItem):
                return member_or_err
            member = member_or_err

            if (
                member.role not in PROJECT_ELEVATED_RECORD_ROLES
                and parent_log.author_id != current_user.id
            ):
                return SyncPushResultItem(
                    entity="site_log_photos",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Insufficient permissions to modify photos on this site log",
                )

            existing = db.get(SiteLogPhoto, item.id)
            if existing is not None:
                if existing.site_log_id != item.site_log_id:
                    return SyncPushResultItem(
                        entity="site_log_photos",
                        id=item.id,
                        status="REJECTED",
                        error_code="FORBIDDEN",
                        error_detail="Cannot move photo to another site log",
                    )
                if existing.storage_uri == item.storage_uri:
                    next_upload_status = existing.upload_status
                elif _has_uploaded_ticket(db, parent_log.project_id, item.storage_uri):
                    next_upload_status = "UPLOADED"
                else:
                    next_upload_status = "PENDING"
                server_version = db.scalar(
                    update(SiteLogPhoto)
                    .where(SiteLogPhoto.id == item.id)
                    .values(
                        storage_uri=item.storage_uri,
                        upload_status=next_upload_status,
                        width=item.width,
                        height=item.height,
                        byte_size=item.byte_size,
                        taken_at=item.taken_at,
                        sort_order=item.sort_order,
                        deleted_at=item.deleted_at,
                    )
                    .returning(SiteLogPhoto.server_version)
                )
            else:
                init_status = (
                    "UPLOADED"
                    if _has_uploaded_ticket(db, parent_log.project_id, item.storage_uri)
                    else "PENDING"
                )
                server_version = db.scalar(
                    pg_insert(SiteLogPhoto)
                    .values(
                        id=item.id,
                        site_log_id=item.site_log_id,
                        storage_uri=item.storage_uri,
                        upload_status=init_status,
                        width=item.width,
                        height=item.height,
                        byte_size=item.byte_size,
                        taken_at=item.taken_at,
                        sort_order=item.sort_order,
                        deleted_at=item.deleted_at,
                    )
                    .returning(SiteLogPhoto.server_version)
                )

        return SyncPushResultItem(
            entity="site_log_photos",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        return SyncPushResultItem(
            entity="site_log_photos",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=safe_public_error_summary(exc, fallback="Photo sync rejected"),
        )


@router.post("/push", response_model=SyncPushResponse)
def sync_push(
    payload: SyncPushRequest,
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyncPushResponse:
    total = (
        len(payload.changes.permits)
        + len(payload.changes.site_logs)
        + len(payload.changes.site_log_photos)
    )
    if total > MAX_PUSH_RECORDS:
        raise ProblemException(
            status_code=413,
            code="BATCH_TOO_LARGE",
            title="Payload Too Large",
            detail=f"Batch contains {total} records; maximum is {MAX_PUSH_RECORDS}",
        )

    project_cache: dict[UUID, Project | None] = {}
    member_cache: dict[UUID, ProjectMember | None] = {}
    results: list[SyncPushResultItem] = []

    for raw_permit in payload.changes.permits:
        results.append(
            _apply_permit_push(
                db,
                current_user,
                raw_permit,
                settings=settings,
                project_cache=project_cache,
                member_cache=member_cache,
            )
        )
    for raw_log in payload.changes.site_logs:
        results.append(
            _apply_site_log_push(
                db,
                current_user,
                raw_log,
                settings=settings,
                project_cache=project_cache,
                member_cache=member_cache,
            )
        )
    for raw_photo in payload.changes.site_log_photos:
        results.append(
            _apply_photo_push(
                db,
                current_user,
                raw_photo,
                settings=settings,
                project_cache=project_cache,
                member_cache=member_cache,
            )
        )

    db.commit()
    return SyncPushResponse(
        server_time=datetime.now(UTC),
        results=results,
    )


@router.get("/pull", response_model=SyncPullResponse)
def sync_pull(
    current_user: Annotated[User, Depends(get_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    since: Annotated[int, Query(ge=0)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    project_id: Annotated[UUID | None, Query()] = None,
) -> SyncPullResponse:
    # End implicit transaction started by auth dependency so REPEATABLE READ starts cleanly.
    db.commit()
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))

    active_pids_stmt = (
        select(ProjectMember.project_id)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == current_user.id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if current_user.organization_id is not None:
        active_pids_stmt = active_pids_stmt.where(
            (Project.organization_id == current_user.organization_id)
            | Project.organization_id.is_(None)
        )
    if project_id is not None:
        active_pids_stmt = active_pids_stmt.where(ProjectMember.project_id == project_id)
    active_project_ids = list(db.scalars(active_pids_stmt))

    q_projects = select(
        literal("projects").cast(String).label("entity"),
        Project.id.cast(String).label("pk1"),
        literal("").cast(String).label("pk2"),
        Project.server_version.cast(BigInteger).label("server_version"),
    ).where(
        Project.id.in_(active_project_ids),
        Project.server_version > since,
    )

    member_filter = (ProjectMember.project_id.in_(active_project_ids)) | (
        ProjectMember.user_id == current_user.id
    )
    q_members = select(
        literal("project_members").cast(String).label("entity"),
        ProjectMember.project_id.cast(String).label("pk1"),
        ProjectMember.user_id.cast(String).label("pk2"),
        ProjectMember.server_version.cast(BigInteger).label("server_version"),
    ).where(
        member_filter,
        ProjectMember.server_version > since,
    )
    if project_id is not None:
        q_members = q_members.where(ProjectMember.project_id == project_id)

    q_permits = select(
        literal("permits").cast(String).label("entity"),
        Permit.id.cast(String).label("pk1"),
        literal("").cast(String).label("pk2"),
        Permit.server_version.cast(BigInteger).label("server_version"),
    ).where(
        Permit.project_id.in_(active_project_ids),
        Permit.server_version > since,
    )

    q_logs = select(
        literal("site_logs").cast(String).label("entity"),
        SiteLog.id.cast(String).label("pk1"),
        literal("").cast(String).label("pk2"),
        SiteLog.server_version.cast(BigInteger).label("server_version"),
    ).where(
        SiteLog.project_id.in_(active_project_ids),
        SiteLog.server_version > since,
    )

    q_photos = (
        select(
            literal("site_log_photos").cast(String).label("entity"),
            SiteLogPhoto.id.cast(String).label("pk1"),
            literal("").cast(String).label("pk2"),
            SiteLogPhoto.server_version.cast(BigInteger).label("server_version"),
        )
        .join(SiteLog, SiteLog.id == SiteLogPhoto.site_log_id)
        .where(
            SiteLog.project_id.in_(active_project_ids),
            SiteLogPhoto.server_version > since,
        )
    )

    combined = union_all(q_projects, q_members, q_permits, q_logs, q_photos).subquery()
    page_rows = db.execute(
        select(
            combined.c.entity,
            combined.c.pk1,
            combined.c.pk2,
            combined.c.server_version,
        )
        .order_by(combined.c.server_version.asc())
        .limit(limit + 1)
    ).all()

    has_more = len(page_rows) > limit
    selected_rows = page_rows[:limit]
    next_cursor = int(selected_rows[-1].server_version) if selected_rows else since

    project_ids_to_fetch: list[UUID] = []
    member_pks_to_fetch: list[tuple[UUID, UUID]] = []
    permit_ids_to_fetch: list[UUID] = []
    log_ids_to_fetch: list[UUID] = []
    photo_ids_to_fetch: list[UUID] = []

    for row in selected_rows:
        entity = row.entity
        if entity == "projects":
            project_ids_to_fetch.append(UUID(row.pk1))
        elif entity == "project_members":
            member_pks_to_fetch.append((UUID(row.pk1), UUID(row.pk2)))
        elif entity == "permits":
            permit_ids_to_fetch.append(UUID(row.pk1))
        elif entity == "site_logs":
            log_ids_to_fetch.append(UUID(row.pk1))
        elif entity == "site_log_photos":
            photo_ids_to_fetch.append(UUID(row.pk1))

    projects_out: list[ProjectResponse] = []
    if project_ids_to_fetch:
        proj_rows = list(
            db.scalars(
                select(Project)
                .where(Project.id.in_(project_ids_to_fetch))
                .order_by(Project.server_version.asc())
            )
        )
        projects_out = [ProjectResponse.model_validate(p) for p in proj_rows]

    members_out: list[MemberResponse] = []
    if member_pks_to_fetch:
        proj_set = {pk[0] for pk in member_pks_to_fetch}
        user_set = {pk[1] for pk in member_pks_to_fetch}
        pk_set = set(member_pks_to_fetch)
        member_rows = db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(
                ProjectMember.project_id.in_(proj_set),
                ProjectMember.user_id.in_(user_set),
            )
            .order_by(ProjectMember.server_version.asc())
        ).all()
        for member, user in member_rows:
            if (member.project_id, member.user_id) in pk_set:
                members_out.append(
                    MemberResponse(
                        project_id=member.project_id,
                        user_id=member.user_id,
                        role=cast(Role, member.role),
                        full_name=user.full_name,
                        email=user.email,
                        deleted_at=member.deleted_at,
                        server_version=member.server_version,
                    )
                )

    permits_out = []
    if permit_ids_to_fetch:
        permit_rows = list(
            db.scalars(
                select(PermitWithStatus)
                .where(PermitWithStatus.id.in_(permit_ids_to_fetch))
                .order_by(PermitWithStatus.server_version.asc())
            )
        )
        permits_out = [
            serialize_permit(p, storage, include_signed_url=False) for p in permit_rows
        ]

    logs_out = []
    if log_ids_to_fetch:
        log_rows = db.execute(
            select(SiteLog, User.full_name)
            .join(User, User.id == SiteLog.author_id)
            .where(SiteLog.id.in_(log_ids_to_fetch))
            .order_by(SiteLog.server_version.asc())
        ).all()
        logs_out = [
            serialize_site_log_pull(log, author_name, storage)
            for log, author_name in log_rows
        ]

    photos_out = []
    if photo_ids_to_fetch:
        photo_rows = list(
            db.scalars(
                select(SiteLogPhoto)
                .where(SiteLogPhoto.id.in_(photo_ids_to_fetch))
                .order_by(SiteLogPhoto.server_version.asc())
            )
        )
        photos_out = [
            serialize_photo(photo, storage, include_signed_url=False) for photo in photo_rows
        ]

    return SyncPullResponse(
        next_cursor=next_cursor,
        has_more=has_more,
        changes=SyncPullChanges(
            projects=projects_out,
            project_members=members_out,
            permits=permits_out,
            site_logs=logs_out,
            site_log_photos=photos_out,
        ),
    )
