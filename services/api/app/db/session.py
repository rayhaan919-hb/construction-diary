from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, normalize_postgres_url


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    url = normalize_postgres_url(database_url or get_settings().sqlalchemy_database_url)
    return create_engine(
        url,
        pool_pre_ping=True,
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
