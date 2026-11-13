from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import BigInteger, String, literal, select, text, union_all, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.errors import ProblemException
from app.db.models import (
    Permit,
    PermitWithStatus,
    Project,
    ProjectMember,
    SiteLog,
    SiteLogPhoto,
    User,
)
from app.db.session import get_db
from app.schemas.auth import Role
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
from app.services.reports import (
    serialize_permit,
    serialize_photo,
    serialize_site_log_pull,
)
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
    entity: Literal["permits", "site_logs", "site_log_photos"],
    record_id: UUID,
    project_id: UUID,
    user_id: UUID,
) -> ProjectMember | SyncPushResultItem:
    project = db.get(Project, project_id)
    if project is None:
        db.rollback()
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="NOT_FOUND",
            error_detail="Project not found",
        )
    if project.deleted_at is not None:
        db.rollback()
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="PROJECT_DELETED",
            error_detail="Project has been deleted",
        )

    member = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if member is None:
        db.rollback()
        return SyncPushResultItem(
            entity=entity,
            id=record_id,
            status="REJECTED",
            error_code="FORBIDDEN",
            error_detail="Active project membership required",
        )
    return member


def _apply_permit_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
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
            error_detail=str(exc),
        )

    try:
        member_or_err = _resolve_active_member_for_push(
            db, "permits", item.id, item.project_id, current_user.id
        )
        if isinstance(member_or_err, SyncPushResultItem):
            return member_or_err
        member = member_or_err

        existing = db.get(Permit, item.id)
        if existing is not None:
            if existing.project_id != item.project_id:
                db.rollback()
                return SyncPushResultItem(
                    entity="permits",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Cannot move permit to another project",
                )
            if member.role != "OWNER" and existing.created_by != current_user.id:
                db.rollback()
                return SyncPushResultItem(
                    entity="permits",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Supervisors may only update permits they created",
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
                    created_by=current_user.id,
                    client_updated_at=item.client_updated_at,
                    deleted_at=item.deleted_at,
                )
                .returning(Permit.server_version)
            )

        db.commit()
        return SyncPushResultItem(
            entity="permits",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        db.rollback()
        return SyncPushResultItem(
            entity="permits",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=str(exc),
        )


def _apply_site_log_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
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
            error_detail=str(exc),
        )

    try:
        member_or_err = _resolve_active_member_for_push(
            db, "site_logs", item.id, item.project_id, current_user.id
        )
        if isinstance(member_or_err, SyncPushResultItem):
            return member_or_err
        member = member_or_err

        existing = db.get(SiteLog, item.id)
        if existing is not None:
            if existing.project_id != item.project_id:
                db.rollback()
                return SyncPushResultItem(
                    entity="site_logs",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Cannot move site log to another project",
                )
            if member.role != "OWNER" and existing.author_id != current_user.id:
                db.rollback()
                return SyncPushResultItem(
                    entity="site_logs",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Supervisors may only update logs they authored",
                )

            if item.audio_uri is None:
                next_audio_status = "NONE"
            elif (
                existing.audio_uri == item.audio_uri
                and existing.audio_upload_status == "UPLOADED"
            ):
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
                update_values["structured_summary"] = (
                    item.structured_summary.model_dump()
                    if item.structured_summary is not None
                    else None
                )

            server_version = db.scalar(
                update(SiteLog)
                .where(SiteLog.id == item.id)
                .values(**update_values)
                .returning(SiteLog.server_version)
            )
        else:
            initial_audio_status = "PENDING" if item.audio_uri is not None else "NONE"
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

        db.commit()
        return SyncPushResultItem(
            entity="site_logs",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        db.rollback()
        return SyncPushResultItem(
            entity="site_logs",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=str(exc),
        )


def _apply_photo_push(
    db: Session,
    current_user: User,
    raw: dict[str, Any],
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
            error_detail=str(exc),
        )

    try:
        parent_log = db.get(SiteLog, item.site_log_id)
        if parent_log is None:
            db.rollback()
            return SyncPushResultItem(
                entity="site_log_photos",
                id=item.id,
                status="REJECTED",
                error_code="NOT_FOUND",
                error_detail="Parent site_log not found",
            )

        member_or_err = _resolve_active_member_for_push(
            db, "site_log_photos", item.id, parent_log.project_id, current_user.id
        )
        if isinstance(member_or_err, SyncPushResultItem):
            return member_or_err
        member = member_or_err
        if member.role != "OWNER" and parent_log.author_id != current_user.id:
            db.rollback()
            return SyncPushResultItem(
                entity="site_log_photos",
                id=item.id,
                status="REJECTED",
                error_code="FORBIDDEN",
                error_detail="Supervisors may only modify photos on logs they authored",
            )

        existing = db.get(SiteLogPhoto, item.id)
        if existing is not None:
            if existing.site_log_id != item.site_log_id:
                db.rollback()
                return SyncPushResultItem(
                    entity="site_log_photos",
                    id=item.id,
                    status="REJECTED",
                    error_code="FORBIDDEN",
                    error_detail="Cannot move photo to another site log",
                )
            next_upload_status = (
                existing.upload_status
                if existing.storage_uri == item.storage_uri
                else "PENDING"
            )
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
            server_version = db.scalar(
                pg_insert(SiteLogPhoto)
                .values(
                    id=item.id,
                    site_log_id=item.site_log_id,
                    storage_uri=item.storage_uri,
                    upload_status="PENDING",
                    width=item.width,
                    height=item.height,
                    byte_size=item.byte_size,
                    taken_at=item.taken_at,
                    sort_order=item.sort_order,
                    deleted_at=item.deleted_at,
                )
                .returning(SiteLogPhoto.server_version)
            )

        db.commit()
        return SyncPushResultItem(
            entity="site_log_photos",
            id=item.id,
            status="APPLIED",
            server_version=server_version,
        )
    except Exception as exc:
        db.rollback()
        return SyncPushResultItem(
            entity="site_log_photos",
            id=item.id,
            status="REJECTED",
            error_code="VALIDATION",
            error_detail=str(exc),
        )


@router.post("/push", response_model=SyncPushResponse)
def sync_push(
    payload: SyncPushRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
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

    results: list[SyncPushResultItem] = []
    for raw_permit in payload.changes.permits:
        results.append(_apply_permit_push(db, current_user, raw_permit))
    for raw_log in payload.changes.site_logs:
        results.append(_apply_site_log_push(db, current_user, raw_log))
    for raw_photo in payload.changes.site_log_photos:
        results.append(_apply_photo_push(db, current_user, raw_photo))

    return SyncPushResponse(
        server_time=datetime.now(UTC),
        results=results,
    )


@router.get("/pull", response_model=SyncPullResponse)
def sync_pull(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    since: Annotated[int, Query(ge=0)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    project_id: Annotated[UUID | None, Query()] = None,
) -> SyncPullResponse:
    # End implicit transaction started by auth dependency so REPEATABLE READ starts cleanly.
    db.commit()
    db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))

    active_pids_stmt = select(ProjectMember.project_id).where(
        ProjectMember.user_id == current_user.id,
        ProjectMember.deleted_at.is_(None),
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
        logs_out = [serialize_site_log_pull(log, author_name) for log, author_name in log_rows]

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
