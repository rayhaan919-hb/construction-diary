from __future__ import annotations

import base64
import logging
from typing import Any

import google.auth
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest

logger = logging.getLogger(__name__)

_SECRET_MANAGER_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class SecretManagerError(RuntimeError):
    """Raised when loading a production secret from Google Secret Manager fails."""


def fetch_gcp_secret(
    secret_name_or_id: str,
    *,
    project_id: str | None = None,
    version: str = "latest",
    timeout_seconds: float = 10.0,
) -> str:
    """Fetch a secret payload from Google Cloud Secret Manager via ADC + REST.

    Accepts either:
    - full resource name: ``projects/<proj>/secrets/<name>/versions/<ver>``
    - ``sm://projects/<proj>/secrets/<name>/versions/<ver>``
    - ``sm://<secret_id>`` or bare ``<secret_id>`` (uses ``project_id``)
    """
    raw = secret_name_or_id.removeprefix("sm://").strip()
    if raw.startswith("projects/"):
        resource_name = (
            raw if "/versions/" in raw else f"{raw.rstrip('/')}/versions/{version}"
        )
    else:
        if not project_id:
            raise SecretManagerError(
                f"Cannot resolve secret '{raw}' without GCP project id"
            )
        resource_name = f"projects/{project_id}/secrets/{raw}/versions/{version}"

    try:
        credentials, detected_project = google.auth.default(scopes=[_SECRET_MANAGER_SCOPE])
        if not project_id and not raw.startswith("projects/") and detected_project:
            resource_name = (
                f"projects/{detected_project}/secrets/{raw}/versions/{version}"
            )
        credentials.refresh(GoogleAuthRequest())  # type: ignore[no-untyped-call]
        token: str | None = getattr(credentials, "token", None)
        if not token:
            raise SecretManagerError("ADC did not yield an access token")

        url = f"https://secretmanager.googleapis.com/v1/{resource_name}:access"
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            raise SecretManagerError(
                f"Secret Manager HTTP {resp.status_code} for {resource_name}"
            )
        data_json: dict[str, Any] = resp.json()
        encoded = data_json.get("payload", {}).get("data")
        if not isinstance(encoded, str) or not encoded:
            raise SecretManagerError(f"Empty secret payload for {resource_name}")
        return base64.b64decode(encoded).decode("utf-8")
    except SecretManagerError:
        raise
    except Exception as exc:
        raise SecretManagerError(
            f"Failed retrieving secret '{resource_name}': {type(exc).__name__}"
        ) from exc
