from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, logs, media, permits, projects, sync, system
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.db.session import create_session_factory
from app.services.extraction_worker import (
    recover_stuck_extractions,
    run_extraction_for_log,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    pending_tasks: set[asyncio.Task[None]] = set()
    try:
        session_factory = create_session_factory()
        stuck_log_ids = recover_stuck_extractions(session_factory)
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

    yield

    for task in list(pending_tasks):
        task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Construction Permit & Site Diary API",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    application.include_router(system.router)
    application.include_router(auth.router)
    application.include_router(projects.router)
    application.include_router(permits.router)
    application.include_router(logs.router)
    application.include_router(media.router)
    application.include_router(sync.router)

    return application


app = create_app()
