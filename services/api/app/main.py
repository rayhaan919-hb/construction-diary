from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import auth, logs, media, permits, projects, saas, sync, system
from app.core.config import Settings, get_settings, validate_runtime_configuration
from app.core.errors import problem_response, register_exception_handlers
from app.core.logging_config import (
    actor_org_id_ctx,
    actor_user_id_ctx,
    configure_structured_logging,
    request_id_ctx,
)
from app.core.rate_limit import metrics_collector, rate_limiter
from app.db.session import create_session_factory
from app.services.extraction_worker import (
    recover_stuck_extractions,
    run_extraction_for_log,
)

logger = logging.getLogger(__name__)

_PROBE_PATHS = frozenset({"/livez", "/healthz", "/readyz"})


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pending_tasks: set[asyncio.Task[None]] = set()
    try:
        session_factory = create_session_factory()
        stuck_log_ids = recover_stuck_extractions(session_factory, settings)
        for log_id in stuck_log_ids:
            task = asyncio.create_task(
                asyncio.to_thread(
                    run_extraction_for_log,
                    log_id,
                    session_factory,
                    settings,
                )
            )
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)
    except Exception:
        logger.warning("Startup extraction recovery skipped (database not ready)")

    try:
        yield
    finally:
        if pending_tasks:
            for task in list(pending_tasks):
                task.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    configure_structured_logging(level=settings.LOG_LEVEL)
    validate_runtime_configuration(settings)

    docs_enabled = settings.ENABLE_API_DOCS and settings.ENV != "production"
    application = FastAPI(
        title="Construction Permit & Site Diary API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    if settings.TRUSTED_HOSTS.strip() and settings.TRUSTED_HOSTS.strip() != "*":
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.trusted_host_list,
        )

    @application.middleware("http")
    async def request_hardening_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        tok_req = request_id_ctx.set(req_id)
        tok_usr = actor_user_id_ctx.set(None)
        tok_org = actor_org_id_ctx.set(None)
        start = time.perf_counter()

        try:
            content_length_raw = request.headers.get("content-length")
            if content_length_raw is not None:
                try:
                    content_length = int(content_length_raw)
                except ValueError:
                    return problem_response(
                        status_code=400,
                        code="VALIDATION",
                        title="Bad Request",
                        detail="Invalid Content-Length header",
                    )
                if content_length > settings.MAX_REQUEST_BODY_BYTES:
                    return problem_response(
                        status_code=413,
                        code="BATCH_TOO_LARGE",
                        title="Payload Too Large",
                        detail="Request body exceeds maximum allowed size",
                    )

            path = request.url.path
            if settings.RATE_LIMIT_REQUESTS_PER_MINUTE > 0 and path not in _PROBE_PATHS:
                forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                client_ip = forwarded or (request.client.host if request.client else "unknown")
                decision = rate_limiter.check(
                    f"global:ip:{client_ip}",
                    settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                    60,
                )
                if not decision.allowed:
                    return problem_response(
                        status_code=429,
                        code="RATE_LIMITED",
                        title="Too Many Requests",
                        detail="Request rate limit exceeded; please slow down.",
                        headers={
                            "Retry-After": str(decision.retry_after_seconds),
                            "X-Request-ID": req_id,
                        },
                    )

            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            metrics_collector.record(response.status_code, elapsed_ms)

            response.headers["X-Request-ID"] = req_id
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            if path.startswith("/v1/"):
                response.headers.setdefault("Cache-Control", "no-store")
            if settings.is_deployed_env:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    "max-age=63072000; includeSubDomains",
                )
            return response
        finally:
            request_id_ctx.reset(tok_req)
            actor_user_id_ctx.reset(tok_usr)
            actor_org_id_ctx.reset(tok_org)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "Stripe-Signature",
            "X-Task-Secret",
            "X-Scheduler-Secret",
        ],
    )

    register_exception_handlers(application)

    application.include_router(system.router)
    application.include_router(auth.router)
    application.include_router(saas.router)
    application.include_router(projects.router)
    application.include_router(permits.router)
    application.include_router(logs.router)
    application.include_router(media.router)
    application.include_router(sync.router)

    return application


app = create_app()
