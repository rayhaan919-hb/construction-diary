from __future__ import annotations

import contextlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging_config import (
    actor_org_id_ctx,
    actor_user_id_ctx,
    redact_mapping,
    redact_text,
    request_id_ctx,
)
from app.db.models import AuditLog, User


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None = None,
    actor_user: User | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_email: str | None = None,
    organization_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an immutable, secret-redacted audit entry in the active session."""
    resolved_user_id = actor_user.id if actor_user is not None else actor_user_id
    resolved_email = actor_user.email if actor_user is not None else actor_email
    resolved_org_id = (
        organization_id
        if organization_id is not None
        else (actor_user.organization_id if actor_user is not None else None)
    )
    if resolved_user_id is None:
        ctx_uid = actor_user_id_ctx.get()
        if ctx_uid:
            with contextlib.suppress(ValueError):
                resolved_user_id = uuid.UUID(ctx_uid)
    if resolved_org_id is None:
        ctx_org = actor_org_id_ctx.get()
        if ctx_org:
            with contextlib.suppress(ValueError):
                resolved_org_id = uuid.UUID(ctx_org)

    entry = AuditLog(
        organization_id=resolved_org_id,
        actor_user_id=resolved_user_id,
        actor_email=resolved_email,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=ip_address[:64] if ip_address else None,
        user_agent=redact_text(user_agent)[:256] if user_agent else None,
        request_id=request_id or request_id_ctx.get(),
        details=redact_mapping(details or {}),
    )
    db.add(entry)
    return entry
