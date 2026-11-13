from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_postgres_url(url: str) -> str:
    """Normalize postgres/postgresql URLs to use the psycopg3 SQLAlchemy dialect."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/site_diary"
    TEST_DATABASE_URL: str = ""

    # Auth
    JWT_SECRET: str = "change_me_to_a_long_random_string"
    ACCESS_TOKEN_TTL_SECONDS: int = 900
    REFRESH_TOKEN_TTL_DAYS: int = 60
    CORS_ORIGINS: str = "http://localhost:3000"

    # Gemini (google-genai SDK)
    USE_MOCK_GEMINI: bool = True
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    EXTRACTION_TIMEOUT_SECONDS: int = 60
    EXTRACTION_MAX_ATTEMPTS: int = 3

    # Storage
    STORAGE_BACKEND: Literal["local", "gcs"] = "local"
    LOCAL_STORAGE_DIR: str = "./.storage"
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    MEDIA_URL_SIGNING_SECRET: str = "change_me_too"
    GCS_BUCKET: str = ""
    SIGNED_URL_TTL_SECONDS: int = 900

    # Permit alerts
    PERMIT_EXPIRING_SOON_DAYS: int = 14
    NOTIFIER: str = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@example.com"
    FCM_PROJECT_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # Dev seed
    SEED_OWNER_EMAIL: str = "owner@example.com"
    SEED_OWNER_PASSWORD: str = "owner12345"
    SEED_SUPERVISOR_EMAIL: str = "supervisor@example.com"
    SEED_SUPERVISOR_PASSWORD: str = "super12345"

    @property
    def sqlalchemy_database_url(self) -> str:
        return normalize_postgres_url(self.DATABASE_URL)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def notifier_channels(self) -> list[str]:
        return [c.strip().lower() for c in self.NOTIFIER.split(",") if c.strip()]

    @property
    def local_storage_path(self) -> Path:
        return Path(self.LOCAL_STORAGE_DIR).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
