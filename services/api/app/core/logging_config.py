from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_user_id_ctx: ContextVar[str | None] = ContextVar("actor_user_id", default=None)
actor_org_id_ctx: ContextVar[str | None] = ContextVar("actor_org_id", default=None)

REDACTED = "[REDACTED]"

_SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "private_key",
    "sig",
    "signature",
)

_BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_SIG_QUERY_RE = re.compile(
    r"([?&](?:sig|signature|token|key|X-Goog-Signature)=)[^&\s]+",
    re.IGNORECASE,
)
_DB_URL_CREDS_RE = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:\s/]+:)[^@\s]+(@)")


def redact_text(value: str) -> str:
    """Scrub secrets, JWTs, signed query signatures, and DB passwords from log/error text."""
    text = _BEARER_RE.sub(r"\1" + REDACTED, value)
    text = _JWT_RE.sub(REDACTED, text)
    text = _SIG_QUERY_RE.sub(r"\1" + REDACTED, text)
    text = _DB_URL_CREDS_RE.sub(r"\1" + REDACTED + r"\2", text)
    return text


def redact_mapping(data: Any, *, depth: int = 0) -> Any:
    """Recursively redact sensitive keys inside structured metadata / audit details."""
    if depth > 6:
        return "[TRUNCATED]"
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            lowered = key_str.lower()
            if any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS):
                cleaned[key_str] = REDACTED
            else:
                cleaned[key_str] = redact_mapping(v, depth=depth + 1)
        return cleaned
    if isinstance(data, list):
        return [redact_mapping(item, depth=depth + 1) for item in data[:50]]
    if isinstance(data, str):
        return redact_text(data[:1000])
    return data


def safe_public_error_summary(exc: Exception, *, fallback: str = "Operation failed") -> str:
    """Return a bounded, non-leaky error summary safe to persist or return to clients."""
    exc_name = type(exc).__name__
    msg = redact_text(str(exc)).strip()
    # Never echo raw SQL or psycopg internal schema statements
    lowered = msg.lower()
    if any(
        token in lowered
        for token in (
            "select ",
            "insert ",
            "update ",
            "delete ",
            "psycopg",
            "sqlalchemy",
            "detail:",
        )
    ):
        return f"{exc_name}: {fallback}"
    first_line = msg.splitlines()[0] if msg else fallback
    return f"{exc_name}: {first_line}"[:300]


class CloudJsonFormatter(logging.Formatter):
    """Structured JSON formatter compatible with Google Cloud Logging."""

    _LEVEL_TO_SEVERITY = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": self._LEVEL_TO_SEVERITY.get(record.levelname, record.levelname),
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        req_id = request_id_ctx.get()
        if req_id:
            payload["request_id"] = req_id
        user_id = actor_user_id_ctx.get()
        if user_id:
            payload["user_id"] = user_id
        org_id = actor_org_id_ctx.get()
        if org_id:
            payload["organization_id"] = org_id

        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload["context"] = redact_mapping(extra)

        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_structured_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(CloudJsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
