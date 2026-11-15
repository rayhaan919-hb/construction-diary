from __future__ import annotations

import logging

from app.core.config import Settings, get_settings
from app.db.session import create_session_factory, get_engine
from app.services.media_cleanup import run_media_cleanup
from app.services.storage import MediaStorageService

logger = logging.getLogger(__name__)


def main(*, dry_run: bool = False) -> None:
    """CLI entrypoint for scheduled orphan media cleanup (Cloud Run Job / cron)."""
    settings: Settings = get_settings()
    settings.resolve_secrets()
    engine = get_engine(settings.sqlalchemy_database_url)
    session_factory = create_session_factory(engine)
    storage = MediaStorageService(settings)
    with session_factory() as db:
        run = run_media_cleanup(
            db,
            storage=storage,
            settings=settings,
            dry_run=dry_run,
        )
        logger.info(
            "Media cleanup run %s finished (%s): tickets=%d reservations=%d incomplete=%d "
            "unattached=%d failed_jobs=%d bytes_reclaimed=%d",
            run.id,
            run.status,
            run.expired_tickets_cleaned,
            run.expired_reservations_cleaned,
            run.incomplete_uploads_cleaned,
            run.unattached_objects_deleted,
            run.failed_jobs_pruned,
            run.bytes_reclaimed,
        )


if __name__ == "__main__":
    main()
