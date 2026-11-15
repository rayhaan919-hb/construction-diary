from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.logging_config import actor_org_id_ctx, actor_user_id_ctx
from app.core.permissions import PROJECT_ELEVATED_RECORD_ROLES
from app.db.models import Organization, Project, ProjectMember, User
from app.db.session import get_db
from app.services.auth import TokenError, decode_access_token
from app.services.saas import ensure_org_active
from app.services.storage import MediaStorageService


def get_storage(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MediaStorageService:
    return _cached_storage(
        settings.STORAGE_BACKEND,
        settings.GCS_BUCKET,
        settings.LOCAL_STORAGE_DIR,
        settings.PUBLIC_API_BASE_URL,
    )


@lru_cache(maxsize=8)
def _cached_storage(
    backend: str,
    gcs_bucket: str,
    local_dir: str,
    public_url: str,
) -> MediaStorageService:
    del backend, gcs_bucket, local_dir, public_url
    return MediaStorageService(get_settings())


def extract_client_meta(request: Request) -> tuple[str | None, str | None]:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else None)
    ua = request.headers.get("user-agent")
    return ip, ua


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    settings: Annotated[Settings, Depends(get_settings)] = ...,  # type: ignore[assignment]
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Missing or malformed Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    try:
        payload = decode_access_token(token, settings)
    except TokenError as exc:
        raise ProblemException(
            status_code=401,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = UUID(str(payload["sub"]))
    except ValueError as exc:
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid subject claim",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise ProblemException(
            status_code=401,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_version = payload.get("tv")
    current_version = int(user.token_version or 0)
    if token_version is None:
        version_mismatch = current_version > 0
    else:
        version_mismatch = (
            isinstance(token_version, bool)
            or not isinstance(token_version, int)
            or token_version != current_version
        )
    if version_mismatch:
        raise ProblemException(
            status_code=401,
            code="TOKEN_REVOKED",
            title="Session Revoked",
            detail="Session has been invalidated; please sign in again",
            headers={"WWW-Authenticate": "Bearer"},
        )

    actor_user_id_ctx.set(str(user.id))
    actor_org_id_ctx.set(str(user.organization_id) if user.organization_id else None)
    return user


def get_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Require password change completion and an active non-suspended organization."""
    if current_user.must_change_password:
        raise ProblemException(
            status_code=403,
            code="PASSWORD_CHANGE_REQUIRED",
            title="Password Change Required",
            detail="You must change your temporary password before accessing workspace resources.",
        )
    if current_user.organization_id is not None:
        org = db.get(Organization, current_user.organization_id)
        ensure_org_active(org)
    return current_user


def _resolve_user_id_and_org(
    db: Session, user_or_id: User | UUID
) -> tuple[UUID, UUID | None]:
    if isinstance(user_or_id, User):
        return user_or_id.id, user_or_id.organization_id
    user_row = db.get(User, user_or_id)
    return user_or_id, (user_row.organization_id if user_row else None)


def require_active_project_member(
    db: Session,
    project_id: UUID,
    user_or_id: User | UUID,
    *,
    allowed_roles: frozenset[str] | None = None,
) -> tuple[Project, ProjectMember]:
    user_id, user_org_id = _resolve_user_id_and_org(db, user_or_id)
    stmt = (
        select(Project, ProjectMember)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
            ProjectMember.user_id == user_id,
            ProjectMember.deleted_at.is_(None),
        )
    )
    row = db.execute(stmt).first()
    if row is None:
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Project not found",
        )
    project, member = row[0], row[1]

    # Strict multi-tenant boundary check: block any cross-company project mismatch
    if (
        user_org_id is not None
        and project.organization_id is not None
        and project.organization_id != user_org_id
    ):
        raise ProblemException(
            status_code=404,
            code="NOT_FOUND",
            title="Not Found",
            detail="Project not found",
        )

    if project.organization_id is not None:
        org = db.get(Organization, project.organization_id)
        ensure_org_active(org)

    if allowed_roles is not None and member.role not in allowed_roles:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Insufficient project permissions for this action",
        )
    return project, member


def require_project_owner(
    db: Session,
    project_id: UUID,
    user_or_id: User | UUID,
) -> tuple[Project, ProjectMember]:
    project, member = require_active_project_member(db, project_id, user_or_id)
    if member.role not in PROJECT_ELEVATED_RECORD_ROLES:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only OWNER, ADMIN, or PROJECT_MANAGER may perform this action",
        )
    return project, member
