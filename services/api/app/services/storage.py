from __future__ import annotations

import hashlib
import hmac
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import quote, unquote
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.errors import FieldError, ProblemException
from app.schemas.media import MediaContentType, MediaKind, UploadTicketResponse

KIND_TO_DIR_AND_EXT: dict[MediaKind, tuple[str, str, MediaContentType]] = {
    "AUDIO": ("audio", "m4a", "audio/mp4"),
    "PHOTO": ("photos", "jpg", "image/jpeg"),
    "PERMIT_DOC": ("permits", "jpg", "image/jpeg"),
}


def build_object_key(kind: MediaKind, project_id: UUID, object_id: UUID) -> str:
    kind_dir, ext, _ = KIND_TO_DIR_AND_EXT[kind]
    return f"projects/{project_id}/{kind_dir}/{object_id}.{ext}"


def validate_kind_content_type(kind: MediaKind, content_type: MediaContentType) -> None:
    _, _, expected_content_type = KIND_TO_DIR_AND_EXT[kind]
    if content_type != expected_content_type:
        raise ProblemException(
            status_code=422,
            code="VALIDATION",
            title="Validation Error",
            detail=f"Media kind {kind} requires content_type {expected_content_type}",
            errors=[
                FieldError(
                    field="content_type",
                    message=f"Expected {expected_content_type} for kind {kind}",
                )
            ],
        )


def _compute_signature(method: str, key: str, exp: int, secret: str) -> str:
    payload = f"{method.upper()}:{key}:{exp}".encode()
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_local_signature(
    method: str,
    key: str,
    sig: str,
    exp: int,
    settings: Settings | None = None,
) -> bool:
    cfg = settings or get_settings()
    if exp < int(time.time()):
        return False
    expected = _compute_signature(method, key, exp, cfg.MEDIA_URL_SIGNING_SECRET)
    return hmac.compare_digest(expected, sig)


def normalize_and_validate_key(raw_key: str) -> str:
    key = unquote(raw_key).lstrip("/")
    if not key or "\\" in key:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid object key",
        )
    parts = key.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid object key",
        )
    return key


def resolve_local_path(key: str, settings: Settings | None = None) -> Path:
    cfg = settings or get_settings()
    clean_key = normalize_and_validate_key(key)
    root = cfg.local_storage_path
    target = (root / clean_key).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ProblemException(
            status_code=403,
            code="FORBIDDEN",
            title="Forbidden",
            detail="Invalid object key path",
        ) from exc
    return target


def parse_storage_uri(storage_uri: str) -> tuple[Literal["local", "gcs"], str, str]:
    """Return (backend, bucket_or_empty, key)."""
    if storage_uri.startswith("local://"):
        return ("local", "", storage_uri[len("local://") :])
    if storage_uri.startswith("gs://"):
        rest = storage_uri[len("gs://") :]
        bucket, _, key = rest.partition("/")
        if not bucket or not key:
            raise ValueError(f"Malformed GCS URI: {storage_uri}")
        return ("gcs", bucket, key)
    raise ValueError(f"Unsupported storage URI scheme: {storage_uri}")


class MediaStorageService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def build_storage_uri(self, key: str) -> str:
        if self.settings.STORAGE_BACKEND == "local":
            return f"local://{key}"
        if not self.settings.GCS_BUCKET:
            raise RuntimeError("GCS_BUCKET must be configured when STORAGE_BACKEND=gcs")
        return f"gs://{self.settings.GCS_BUCKET}/{key}"

    def sign_local_url(
        self, method: Literal["PUT", "GET"], key: str, ttl_seconds: int
    ) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        exp = int(expires_at.timestamp())
        sig = _compute_signature(
            method, key, exp, self.settings.MEDIA_URL_SIGNING_SECRET
        )
        encoded_key = quote(key, safe="")
        base = self.settings.PUBLIC_API_BASE_URL.rstrip("/")
        return (f"{base}/v1/media/local/{encoded_key}?sig={sig}&exp={exp}", expires_at)

    def _sign_gcs_url(
        self,
        bucket_name: str,
        key: str,
        method: Literal["PUT", "GET"],
        ttl_seconds: int,
        content_type: str | None = None,
    ) -> tuple[str, datetime]:
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        if content_type is not None:
            url = str(
                blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=ttl_seconds),
                    method=method,
                    content_type=content_type,
                )
            )
        else:
            url = str(
                blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(seconds=ttl_seconds),
                    method=method,
                )
            )
        return (url, expires_at)

    def create_upload_ticket(
        self,
        kind: MediaKind,
        project_id: UUID,
        object_id: UUID,
        content_type: MediaContentType,
    ) -> UploadTicketResponse:
        validate_kind_content_type(kind, content_type)
        key = build_object_key(kind, project_id, object_id)
        storage_uri = self.build_storage_uri(key)
        ttl = self.settings.SIGNED_URL_TTL_SECONDS

        if self.settings.STORAGE_BACKEND == "local":
            upload_url, expires_at = self.sign_local_url("PUT", key, ttl)
        else:
            upload_url, expires_at = self._sign_gcs_url(
                bucket_name=self.settings.GCS_BUCKET,
                key=key,
                method="PUT",
                ttl_seconds=ttl,
                content_type=content_type,
            )

        return UploadTicketResponse(
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": content_type},
            storage_uri=storage_uri,
            expires_at=expires_at,
        )

    def sign_get_url(
        self, storage_uri: str | None, ttl_seconds: int = 3600
    ) -> str | None:
        if not storage_uri:
            return None
        try:
            scheme, bucket, key = parse_storage_uri(storage_uri)
        except ValueError:
            return None
        if scheme == "local":
            if self.settings.STORAGE_BACKEND != "local":
                return None
            url, _ = self.sign_local_url("GET", key, ttl_seconds)
            return url
        url, _ = self._sign_gcs_url(
            bucket_name=bucket,
            key=key,
            method="GET",
            ttl_seconds=ttl_seconds,
        )
        return url

    def exists(self, storage_uri: str) -> bool:
        try:
            scheme, bucket, key = parse_storage_uri(storage_uri)
        except ValueError:
            return False
        if scheme == "local":
            if self.settings.STORAGE_BACKEND != "local":
                return False
            path = resolve_local_path(key, self.settings)
            return path.is_file()
        from google.cloud import storage

        client = storage.Client()
        return bool(client.bucket(bucket).blob(key).exists())

    def read_bytes(self, storage_uri: str) -> bytes:
        scheme, bucket, key = parse_storage_uri(storage_uri)
        if scheme == "local":
            path = resolve_local_path(key, self.settings)
            if not path.is_file():
                raise FileNotFoundError(f"Local storage object missing: {storage_uri}")
            return path.read_bytes()
        from google.cloud import storage

        client = storage.Client()
        return bytes(client.bucket(bucket).blob(key).download_as_bytes())

    def write_local_bytes(self, key: str, data: bytes) -> Path:
        path = resolve_local_path(key, self.settings)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False, prefix=".tmp_"
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
        return path

    def read_local_bytes(self, key: str) -> bytes | None:
        path = resolve_local_path(key, self.settings)
        if not path.is_file():
            return None
        return path.read_bytes()
