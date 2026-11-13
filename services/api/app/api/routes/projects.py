from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_storage,
    require_active_project_member,
    require_project_owner,
)
from app.core.errors import ProblemException
from app.db.models import PermitWithStatus, Project, ProjectMember, SiteLog, User
from app.db.session import get_db
from app.schemas.auth import Role
from app.schemas.projects import (
    InviteMemberRequest,
    InviteMemberResponse,
    MemberResponse,
    ProjectInput,
    ProjectPatch,
    ProjectResponse,
    ProjectSummaryResponse,
    ProjectTodayStats,
)
from app.services.auth import generate_temporary_password, hash_password
from app.services.reports import (
    compute_permit_health,
    dedupe_strings_ci,
    serialize_permit,
)
from app.services.storage import MediaStorageService

router = APIRouter(prefix="/v1/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> list[ProjectSummaryResponse]:
    projects = list(
        db.scalars(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                Project.deleted_at.is_(None),
                ProjectMember.user_id == current_user.id,
                ProjectMember.deleted_at.is_(None),
            )
            .order_by(Project.created_at.desc(), Project.name.asc())
        )
    )
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    permit_rows = list(
        db.scalars(
            select(PermitWithStatus)
            .where(
                PermitWithStatus.project_id.in_(project_ids),
                PermitWithStatus.deleted_at.is_(None),
            )
            .order_by(PermitWithStatus.expiry_date.asc(), PermitWithStatus.created_at.asc())
        )
    )
    permits_by_project: dict[UUID, list[PermitWithStatus]] = defaultdict(list)
    for permit in permit_rows:
        permits_by_project[permit.project_id].append(permit)

    today_by_project = {
        p.id: datetime.now(ZoneInfo(p.timezone)).date() for p in projects
    }
    target_dates = set(today_by_project.values())

    logs = list(
        db.scalars(
            select(SiteLog)
            .where(
                SiteLog.project_id.in_(project_ids),
                SiteLog.deleted_at.is_(None),
                SiteLog.log_date.in_(target_dates),
            )
            .order_by(SiteLog.recorded_at.asc())
        )
    )
    logs_by_project: dict[UUID, list[SiteLog]] = defaultdict(list)
    for log in logs:
        if log.log_date == today_by_project[log.project_id]:
            logs_by_project[log.project_id].append(log)

    summaries: list[ProjectSummaryResponse] = []
    for project in projects:
        today_date = today_by_project[project.id]
        today_logs = logs_by_project[project.id]

        labor_counts: list[int] = []
        raw_blockers: list[str] = []
        last_log_at: datetime | None = None

        for log in today_logs:
            if last_log_at is None or log.recorded_at > last_log_at:
                last_log_at = log.recorded_at
            summary = log.structured_summary
            if summary:
                labor_val = summary.get("labor_count")
                if isinstance(labor_val, int):
                    labor_counts.append(labor_val)
                blockers_val = summary.get("blockers")
                if isinstance(blockers_val, list):
                    raw_blockers.extend(str(item) for item in blockers_val)

        proj_permits = permits_by_project[project.id]
        permit_health = compute_permit_health(proj_permits)
        next_permit = (
            serialize_permit(proj_permits[0], storage) if proj_permits else None
        )

        summaries.append(
            ProjectSummaryResponse(
                project=ProjectResponse.model_validate(project),
                today=ProjectTodayStats(
                    log_date=today_date,
                    labor_max=max(labor_counts) if labor_counts else None,
                    log_count=len(today_logs),
                    last_log_at=last_log_at,
                ),
                permit_health=permit_health,
                next_expiring_permit=next_permit,
                open_blockers_count=len(dedupe_strings_ci(raw_blockers)),
            )
        )

    return summaries


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    payload: ProjectInput,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    if current_user.role != "OWNER":
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only OWNER users can create projects",
        )

    project = Project(
        name=payload.name,
        site_address=payload.site_address,
        owner_phone=payload.owner_phone,
        timezone=payload.timezone,
        allow_photo_gps=payload.allow_photo_gps,
        created_by=current_user.id,
    )
    db.add(project)
    db.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="OWNER",
    )
    db.add(member)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    project, _ = require_active_project_member(db, project_id, current_user.id)
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    payload: ProjectPatch,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    project, _ = require_project_owner(db, project_id, current_user.id)
    fields_set = payload.model_fields_set

    if "name" in fields_set and payload.name is not None:
        project.name = payload.name
    if "site_address" in fields_set and payload.site_address is not None:
        project.site_address = payload.site_address
    if "owner_phone" in fields_set:
        project.owner_phone = payload.owner_phone
    if "timezone" in fields_set and payload.timezone is not None:
        project.timezone = payload.timezone
    if "allow_photo_gps" in fields_set and payload.allow_photo_gps is not None:
        project.allow_photo_gps = payload.allow_photo_gps

    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    project, _ = require_project_owner(db, project_id, current_user.id)
    project.deleted_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/members", response_model=list[MemberResponse])
def list_members(
    project_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MemberResponse]:
    require_active_project_member(db, project_id, current_user.id)
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.deleted_at.is_(None),
        )
        .order_by(ProjectMember.created_at.asc())
    ).all()
    return [
        MemberResponse(
            project_id=member.project_id,
            user_id=member.user_id,
            role=cast(Role, member.role),
            full_name=user.full_name,
            email=user.email,
            deleted_at=member.deleted_at,
            server_version=member.server_version,
        )
        for member, user in rows
    ]


@router.post(
    "/{project_id}/members",
    response_model=InviteMemberResponse,
    status_code=201,
)
def invite_member(
    project_id: UUID,
    payload: InviteMemberRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> InviteMemberResponse:
    require_project_owner(db, project_id, current_user.id)

    normalized_email = str(payload.email).strip().lower()
    existing_user = db.scalar(
        select(User).where(text("LOWER(email) = :email")).params(email=normalized_email)
    )

    temporary_password: str | None = None
    if existing_user is None:
        temporary_password = generate_temporary_password()
        target_user = User(
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            full_name=payload.full_name.strip(),
            role="SUPERVISOR",
            preferred_locale="en",
            must_change_password=True,
        )
        db.add(target_user)
        db.flush()
    else:
        target_user = existing_user

    existing_member = db.get(ProjectMember, (project_id, target_user.id))
    if existing_member is not None:
        if existing_member.deleted_at is None:
            raise ProblemException(
                status_code=409,
                code="CONFLICT",
                title="Conflict",
                detail="User is already an active member of this project",
            )
        existing_member.deleted_at = None
        existing_member.role = target_user.role
        member_row = existing_member
    else:
        member_row = ProjectMember(
            project_id=project_id,
            user_id=target_user.id,
            role=target_user.role,
        )
        db.add(member_row)

    db.commit()
    db.refresh(member_row)

    return InviteMemberResponse(
        member=MemberResponse(
            project_id=member_row.project_id,
            user_id=member_row.user_id,
            role=cast(Role, member_row.role),
            full_name=target_user.full_name,
            email=target_user.email,
            deleted_at=member_row.deleted_at,
            server_version=member_row.server_version,
        ),
        temporary_password=temporary_password,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    require_project_owner(db, project_id, current_user.id)
    target = db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    if target is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Member not found",
        )
    target.deleted_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)
