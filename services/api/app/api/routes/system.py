from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_storage
from app.core.config import Settings, get_settings
from app.core.errors import ProblemException
from app.core.permissions import ORG_ADMIN_ROLES
from app.core.rate_limit import metrics_collector
from app.db.models import ExtractionJob, User
from app.db.session import get_db
from app.schemas.media import MediaCleanupRunResponse
from app.services.media_cleanup import run_media_cleanup
from app.services.storage import MediaStorageService

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    database: str
    storage: str
    environment: str
    pending_extraction_jobs: int
    failed_extraction_jobs: int
    timestamp: datetime


class MetricsResponse(BaseModel):
    requests_total: int
    errors_4xx: int
    errors_5xx: int
    avg_latency_ms: float
    max_latency_ms: float
    pending_extraction_jobs: int
    processing_extraction_jobs: int
    failed_extraction_jobs: int


@router.get("/livez", response_model=HealthResponse)
def livez() -> HealthResponse:
    """Process-only liveness check without external dependencies."""
    return HealthResponse(status="ok")


@router.get("/healthz", response_model=HealthResponse)
def healthz(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise ProblemException(
            status_code=503,
            code="DB_UNAVAILABLE",
            title="Service Unavailable",
            detail="Database connectivity check failed",
        ) from exc
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse)
def readyz(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
) -> ReadinessResponse:
    """Deep readiness probe checking PostgreSQL connectivity, schema migrations, and storage."""
    try:
        db.execute(text("SELECT 1"))
        has_orgs = bool(
            db.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'organizations')"
                )
            )
        )
        if not has_orgs:
            raise RuntimeError("Missing required schema tables")
        pending_jobs = int(
            db.scalar(
                select(func.count())
                .select_from(ExtractionJob)
                .where(ExtractionJob.status == "PENDING")
            )
            or 0
        )
        failed_jobs = int(
            db.scalar(
                select(func.count())
                .select_from(ExtractionJob)
                .where(ExtractionJob.status == "FAILED")
            )
            or 0
        )
    except Exception as exc:
        raise ProblemException(
            status_code=503,
            code="NOT_READY",
            title="Service Not Ready",
            detail="Database readiness check failed",
        ) from exc

    storage_state = "local" if storage.backend == "local" else f"gcs:{settings.GCS_BUCKET}"
    return ReadinessResponse(
        status="ready",
        database="ok",
        storage=storage_state,
        environment=settings.ENV,
        pending_extraction_jobs=pending_jobs,
        failed_extraction_jobs=failed_jobs,
        timestamp=datetime.now(UTC),
    )


@router.get("/v1/system/metrics", response_model=MetricsResponse)
def get_system_metrics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MetricsResponse:
    if current_user.role not in ORG_ADMIN_ROLES:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Only OWNER or ADMIN users can inspect runtime metrics",
        )
    pending = int(
        db.scalar(
            select(func.count())
            .select_from(ExtractionJob)
            .where(ExtractionJob.status == "PENDING")
        )
        or 0
    )
    processing = int(
        db.scalar(
            select(func.count())
            .select_from(ExtractionJob)
            .where(ExtractionJob.status == "PROCESSING")
        )
        or 0
    )
    failed = int(
        db.scalar(
            select(func.count())
            .select_from(ExtractionJob)
            .where(ExtractionJob.status == "FAILED")
        )
        or 0
    )
    snap = metrics_collector.snapshot()
    return MetricsResponse(
        requests_total=int(snap["requests_total"]),
        errors_4xx=int(snap["errors_4xx"]),
        errors_5xx=int(snap["errors_5xx"]),
        avg_latency_ms=float(snap["avg_latency_ms"]),
        max_latency_ms=float(snap["max_latency_ms"]),
        pending_extraction_jobs=pending,
        processing_extraction_jobs=processing,
        failed_extraction_jobs=failed,
    )


@router.post("/v1/internal/cron/permit-alerts")
def trigger_permit_alerts_cron(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    x_scheduler_secret: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    """Authenticated endpoint for Cloud Scheduler to trigger daily permit expiry alerts."""
    expected = settings.SCHEDULER_SHARED_SECRET.strip()
    if not expected or not x_scheduler_secret or not hmac.compare_digest(
        x_scheduler_secret, expected
    ):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid scheduler authorization",
        )
    from app.jobs.permit_alerts import run_permit_alerts

    sent = run_permit_alerts(db, settings=settings)
    return {"alerts_dispatched": sent}


@router.post("/v1/internal/tasks/media-cleanup", response_model=MediaCleanupRunResponse)
def trigger_media_cleanup_task(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[MediaStorageService, Depends(get_storage)],
    dry_run: bool = False,
    x_scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
    x_task_secret: Annotated[str | None, Header(alias="X-Task-Secret")] = None,
) -> MediaCleanupRunResponse:
    """Authenticated internal cron/Cloud Task endpoint for orphan media cleanup."""
    expected_scheduler = settings.SCHEDULER_SHARED_SECRET.strip()
    expected_task = settings.CLOUD_TASKS_SHARED_SECRET.strip()
    if not expected_scheduler and not expected_task:
        raise ProblemException(
            status_code=503,
            code="SERVICE_MISCONFIGURED",
            title="Service Misconfigured",
            detail="Scheduler or Cloud Tasks secret must be configured for media cleanup",
        )
    authorized = False
    if expected_scheduler and x_scheduler_secret:
        authorized = hmac.compare_digest(x_scheduler_secret, expected_scheduler)
    if not authorized and expected_task and x_task_secret:
        authorized = hmac.compare_digest(x_task_secret, expected_task)
    if not authorized:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid internal cleanup authorization",
        )

    run = run_media_cleanup(db, storage=storage, settings=settings, dry_run=dry_run)
    return MediaCleanupRunResponse(
        id=run.id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        dry_run=run.dry_run,
        expired_tickets_cleaned=run.expired_tickets_cleaned,
        expired_reservations_cleaned=run.expired_reservations_cleaned,
        incomplete_uploads_cleaned=run.incomplete_uploads_cleaned,
        unattached_objects_deleted=run.unattached_objects_deleted,
        failed_jobs_pruned=run.failed_jobs_pruned,
        bytes_reclaimed=run.bytes_reclaimed,
    )
