from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secrets import fetch_gcp_secret

EnvironmentName = Literal["development", "test", "staging", "production"]

_INSECURE_SECRET_MARKERS = (
    "change_me",
    "change-me",
    "changeme",
    "default",
    "dev-secret",
    "dev-insecure",
    "insecure",
    "placeholder",
    "secret123",
    "test-jwt",
    "test-media",
    "owner12345",
    "super12345",
    "password",
    "example",
)

# Ephemeral per-process fallback keys used ONLY in local dev when env vars are unset.
_DEV_EPHEMERAL_JWT_SECRET = secrets.token_urlsafe(48)
_DEV_EPHEMERAL_MEDIA_SECRET = secrets.token_urlsafe(48)


def normalize_postgres_url(url: str) -> str:
    """Force SQLAlchemy psycopg v3 driver regardless of postgresql:// scheme."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _is_weak_secret(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < 32:
        return True
    lowered = stripped.lower()
    if any(marker in lowered for marker in _INSECURE_SECRET_MARKERS):
        return True
    return len(set(stripped)) < 8


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(Path(__file__).resolve().parents[4] / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: EnvironmentName = Field(
        default_factory=lambda: (
            "test" if os.getenv("PYTEST_CURRENT_TEST") else "development"
        )
    )
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"
    ENABLE_API_DOCS: bool = True
    TRUSTED_HOSTS: str = "*"

    # Database & pooling
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/site_diary"
    TEST_DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 30000

    # Authentication, JWT & Security
    JWT_SECRET: str = ""
    JWT_ISSUER: str = "site-diary-api"
    JWT_AUDIENCE: str = "site-diary-clients"
    ACCESS_TOKEN_TTL_SECONDS: int = 900
    REFRESH_TOKEN_TTL_DAYS: int = 60
    CORS_ORIGINS: str = "http://localhost:3000"
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    PASSWORD_RESET_TTL_MINUTES: int = 30
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 180
    RATE_LIMIT_AUTH_PER_MINUTE: int = 30
    RATE_LIMIT_MEDIA_UPLOADS_PER_MINUTE: int = 60
    MAX_REQUEST_BODY_BYTES: int = 26_214_400

    # AI Extraction & Durable Queue
    USE_MOCK_GEMINI: bool = True
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str = ""
    GOOGLE_GENAI_USE_VERTEXAI: bool = False
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    EXTRACTION_TIMEOUT_SECONDS: int = 60
    EXTRACTION_MAX_ATTEMPTS: int = 3
    EXTRACTION_STALE_LEASE_SECONDS: int = 300
    CLOUD_TASKS_QUEUE_PATH: str = ""
    CLOUD_TASKS_HANDLER_URL: str = ""
    CLOUD_TASKS_INVOKER_SA_EMAIL: str = ""
    CLOUD_TASKS_SHARED_SECRET: str = ""

    # Media Storage & Secret Manager
    STORAGE_BACKEND: Literal["local", "gcs"] = "local"
    LOCAL_STORAGE_DIR: str = "./.storage"
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"
    MEDIA_URL_SIGNING_SECRET: str = ""
    GCS_BUCKET: str = ""
    SIGNED_URL_TTL_SECONDS: int = 900
    MEDIA_RESERVATION_TTL_SECONDS: int = 3600
    MEDIA_ORPHAN_GRACE_SECONDS: int = 86400
    MEDIA_FAILED_JOB_RETENTION_DAYS: int = 30
    GCP_SECRET_MANAGER_ENABLED: bool = False
    SECRET_MANAGER_PROJECT_ID: str = ""

    # Alerts & Notifications
    PERMIT_EXPIRING_SOON_DAYS: int = 14
    NOTIFIER: str = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@example.com"
    FCM_PROJECT_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    SCHEDULER_SHARED_SECRET: str = ""

    # SaaS & Billing (configurable external credentials)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    STRIPE_PRICE_ENTERPRISE: str = ""
    BILLING_WEBHOOK_MAX_AGE_SECONDS: int = 300

    # Explicit opt-in dev seeding (must NEVER be used in staging/production)
    ENABLE_DEV_SEED: bool = False
    SEED_OWNER_EMAIL: str = "owner@example.com"
    SEED_OWNER_PASSWORD: str = ""
    SEED_SUPERVISOR_EMAIL: str = "supervisor@example.com"
    SEED_SUPERVISOR_PASSWORD: str = ""

    @property
    def effective_jwt_secret(self) -> str:
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self.ENV in ("development", "test"):
            return _DEV_EPHEMERAL_JWT_SECRET
        return ""

    @property
    def effective_media_secret(self) -> str:
        if self.MEDIA_URL_SIGNING_SECRET:
            return self.MEDIA_URL_SIGNING_SECRET
        if self.ENV in ("development", "test"):
            return _DEV_EPHEMERAL_MEDIA_SECRET
        return ""

    @property
    def sqlalchemy_database_url(self) -> str:
        return normalize_postgres_url(self.DATABASE_URL)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.TRUSTED_HOSTS.split(",") if host.strip()]

    @property
    def is_deployed_env(self) -> bool:
        return self.ENV in ("staging", "production")

    @property
    def notifier_channels(self) -> list[str]:
        return [ch.strip().lower() for ch in self.NOTIFIER.split(",") if ch.strip()]

    def resolve_secrets(self) -> None:
        """Resolve any sm:// references (or configured Secret Manager fields) at startup."""
        proj = self.SECRET_MANAGER_PROJECT_ID or self.GOOGLE_CLOUD_PROJECT or None
        secret_fields = (
            "JWT_SECRET",
            "MEDIA_URL_SIGNING_SECRET",
            "DATABASE_URL",
            "SMTP_PASSWORD",
            "GEMINI_API_KEY",
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "CLOUD_TASKS_SHARED_SECRET",
            "SCHEDULER_SHARED_SECRET",
        )
        for field_name in secret_fields:
            current = getattr(self, field_name)
            if isinstance(current, str) and current.startswith("sm://"):
                resolved = fetch_gcp_secret(current, project_id=proj)
                setattr(self, field_name, resolved)
            elif (
                self.GCP_SECRET_MANAGER_ENABLED
                and not current
                and field_name in ("JWT_SECRET", "MEDIA_URL_SIGNING_SECRET")
            ):
                secret_id = f"site-diary-{field_name.lower().replace('_', '-')}"
                resolved = fetch_gcp_secret(secret_id, project_id=proj)
                setattr(self, field_name, resolved)


def validate_runtime_configuration(settings: Settings) -> None:
    """Fail closed at startup if staging/production settings are missing or insecure."""
    settings.resolve_secrets()
    if not settings.is_deployed_env:
        return

    errors: list[str] = []

    if _is_weak_secret(settings.JWT_SECRET):
        errors.append(
            "JWT_SECRET must be set to a cryptographically strong value (>= 32 chars)"
        )
    if _is_weak_secret(settings.MEDIA_URL_SIGNING_SECRET):
        errors.append(
            "MEDIA_URL_SIGNING_SECRET must be set to a strong value (>= 32 chars)"
        )
    if (
        settings.JWT_SECRET
        and settings.MEDIA_URL_SIGNING_SECRET
        and settings.JWT_SECRET == settings.MEDIA_URL_SIGNING_SECRET
    ):
        errors.append("MEDIA_URL_SIGNING_SECRET must differ from JWT_SECRET")

    if settings.ENABLE_DEV_SEED:
        errors.append("ENABLE_DEV_SEED must be false in staging/production")
    if settings.SEED_OWNER_PASSWORD or settings.SEED_SUPERVISOR_PASSWORD:
        errors.append("SEED_*_PASSWORD must not be configured in staging/production")

    origins = settings.cors_origin_list
    if not origins or "*" in origins:
        errors.append("CORS_ORIGINS must specify explicit origins (wildcard '*' disallowed)")

    if settings.ENV == "production":
        if "postgres:postgres@" in settings.DATABASE_URL:
            errors.append("DATABASE_URL must not use default development credentials")
        if settings.USE_MOCK_GEMINI:
            errors.append("USE_MOCK_GEMINI must be false in production")
        if settings.STORAGE_BACKEND != "gcs" or not settings.GCS_BUCKET.strip():
            errors.append("Production requires STORAGE_BACKEND=gcs and non-empty GCS_BUCKET")
        parsed_pub = urlparse(settings.PUBLIC_API_BASE_URL)
        if parsed_pub.scheme != "https" or parsed_pub.hostname in (
            None,
            "localhost",
            "127.0.0.1",
            "10.0.2.2",
        ):
            errors.append(
                "PUBLIC_API_BASE_URL must be an external https:// URL in production"
            )
        if any(not origin.startswith("https://") for origin in origins):
            errors.append("CORS_ORIGINS must use https:// in production")

    if errors:
        raise RuntimeError(
            "Unsafe runtime configuration for ENV="
            f"{settings.ENV}: " + "; ".join(errors)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
