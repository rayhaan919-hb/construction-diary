from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, normalize_postgres_url


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = normalize_postgres_url(database_url or settings.sqlalchemy_database_url)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args={
            "options": f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"
        },
        future=True,
    )


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    target_engine = engine or get_engine()
    return sessionmaker(
        bind=target_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    session_factory = create_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
