from __future__ import annotations

import hashlib
import hmac
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from uuid import UUID

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import storage as gcs

from app.core.config import Settings, get_settings
from app.services.media_security import (
    KIND_CONTENT_TYPES,
    build_immutable_object_key,
    sanitize_relative_object_key,
)

MediaKindStr = Literal["AUDIO", "PHOTO", "PERMIT_DOC"]

EXT_CONTENT_TYPE_MAP: dict[str, str] = {
    ".m4a": "audio/mp4",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


def build_object_key(
    project_id: UUID | str,
    kind: MediaKindStr,
    object_id: UUID | str,
    content_type: str,
    *,
    ticket_id: UUID | str | None = None,
) -> str:
    if ticket_id is None:
        ext = KIND_CONTENT_TYPES[kind][content_type]
        kind_dir = {"AUDIO": "audio", "PHOTO": "photos", "PERMIT_DOC": "permits"}[kind]
        return f"projects/{project_id}/{kind_dir}/{object_id}{ext}"
    return build_immutable_object_key(project_id, kind, object_id, ticket_id, content_type)


@dataclass(frozen=True)
class UploadTicketResult:
    upload_url: str
    headers: dict[str, str]
    storage_uri: str
    object_key: str
    expires_at: datetime


@dataclass(frozen=True)
class StoredObjectInfo:
    exists: bool
    byte_size: int | None
    content_type: str | None
    header_bytes: bytes


class MediaStorageService:
    """Abstraction over local filesystem signed URLs and GCS V4 signed URLs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._gcs_client: gcs.Client | None = None

    @property
    def backend(self) -> Literal["local", "gcs"]:
        return self.settings.STORAGE_BACKEND

    @property
    def local_root(self) -> Path:
        root = Path(self.settings.LOCAL_STORAGE_DIR).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _get_gcs_client(self) -> gcs.Client:
        if self._gcs_client is None:
            self._gcs_client = gcs.Client()
        return self._gcs_client

    def to_storage_uri(self, object_key: str) -> str:
        if self.backend == "gcs":
            return f"gs://{self.settings.GCS_BUCKET}/{object_key}"
        return f"local://{object_key}"

    def parse_storage_uri(self, storage_uri: str) -> tuple[Literal["local", "gcs"], str, str]:
        if storage_uri.startswith("local://"):
            key = sanitize_relative_object_key(storage_uri[len("local://") :])
            if key is None:
                raise ValueError("Invalid local storage URI")
            return "local", "", key
        if storage_uri.startswith("gs://"):
            rest = storage_uri[len("gs://") :]
            bucket, _, key = rest.partition("/")
            clean_key = sanitize_relative_object_key(key)
            if not bucket or clean_key is None:
                raise ValueError(f"Invalid GCS URI: {storage_uri}")
            if self.settings.GCS_BUCKET and bucket != self.settings.GCS_BUCKET:
                raise ValueError("Cross-bucket storage URI is forbidden")
            return "gcs", bucket, clean_key
        raise ValueError(f"Unsupported storage URI scheme: {storage_uri}")

    def safe_local_path(self, object_key: str) -> Path:
        clean_key = sanitize_relative_object_key(object_key)
        if clean_key is None:
            raise ValueError("Invalid object key")
        root = self.local_root
        candidate = (root / clean_key).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Object key escapes local storage root") from exc
        return candidate

    def _local_signature(
        self,
        method: str,
        object_key: str,
        expires_epoch: int,
        ticket_id: str = "",
    ) -> str:
        payload = f"{method.upper()}:{object_key}:{expires_epoch}:{ticket_id}".encode()
        return hmac.new(
            self.settings.effective_media_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    def verify_local_signature(
        self,
        method: str,
        object_key: str,
        expires_epoch: int,
        sig: str,
        *,
        ticket_id: str = "",
    ) -> bool:
        if expires_epoch < int(datetime.now(UTC).timestamp()):
            return False
        expected = self._local_signature(method, object_key, expires_epoch, ticket_id)
        if hmac.compare_digest(expected, sig):
            return True
        if not ticket_id:
            # Backward compat signature check only for GET URLs without ticket_id
            legacy = self._local_signature(method, object_key, expires_epoch, "")
            return hmac.compare_digest(legacy, sig)
        return False

    def _sign_gcs_url(
        self,
        *,
        bucket_name: str,
        object_key: str,
        method: str,
        ttl_seconds: int,
        content_type: str | None = None,
        extension_headers: dict[str, str] | None = None,
    ) -> str:
        client = self._get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_key)

        creds, _ = google.auth.default()
        if hasattr(creds, "sign_bytes"):
            signing_creds = creds
        else:
            auth_req = GoogleAuthRequest()
            creds.refresh(auth_req)  # type: ignore[no-untyped-call]
            sa_email = getattr(creds, "service_account_email", None)
            if not sa_email:
                raise RuntimeError(
                    "Active GCP credentials cannot sign GCS URLs; bind a service account."
                )
            signing_creds = impersonated_credentials.Credentials(  # type: ignore[no-untyped-call]
                source_credentials=creds,
                target_principal=sa_email,
                target_scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
            )

        kwargs: dict[str, object] = {
            "version": "v4",
            "expiration": timedelta(seconds=ttl_seconds),
            "method": method,
            "credentials": signing_creds,
        }
        if content_type:
            kwargs["content_type"] = content_type
        if extension_headers:
            kwargs["headers"] = extension_headers
        return str(blob.generate_signed_url(**kwargs))

    def create_upload_ticket(
        self,
        *,
        project_id: UUID | str,
        kind: MediaKindStr,
        object_id: UUID | str,
        content_type: str,
        ticket_id: UUID | str,
        expected_byte_size: int,
    ) -> UploadTicketResult:
        object_key = build_object_key(
            project_id,
            kind,
            object_id,
            content_type,
            ticket_id=ticket_id,
        )
        ttl = self.settings.SIGNED_URL_TTL_SECONDS
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
        expires_epoch = int(expires_at.timestamp())
        storage_uri = self.to_storage_uri(object_key)

        if self.backend == "gcs":
            ext_headers = {
                "x-goog-if-generation-match": "0",
                "x-goog-content-length-range": f"1,{expected_byte_size}",
            }
            url = self._sign_gcs_url(
                bucket_name=self.settings.GCS_BUCKET,
                object_key=object_key,
                method="PUT",
                ttl_seconds=ttl,
                content_type=content_type,
                extension_headers=ext_headers,
            )
            return UploadTicketResult(
                upload_url=url,
                headers={"Content-Type": content_type, **ext_headers},
                storage_uri=storage_uri,
                object_key=object_key,
                expires_at=expires_at,
            )

        ticket_str = str(ticket_id)
        sig = self._local_signature("PUT", object_key, expires_epoch, ticket_str)
        base = self.settings.PUBLIC_API_BASE_URL.rstrip("/")
        query = urlencode({"exp": expires_epoch, "sig": sig, "ticket": ticket_str})
        return UploadTicketResult(
            upload_url=f"{base}/v1/media/local/{object_key}?{query}",
            headers={"Content-Type": content_type},
            storage_uri=storage_uri,
            object_key=object_key,
            expires_at=expires_at,
        )

    def sign_get_url(self, storage_uri: str, ttl_seconds: int = 3600) -> str:
        scheme, bucket, object_key = self.parse_storage_uri(storage_uri)
        if scheme == "gcs":
            return self._sign_gcs_url(
                bucket_name=bucket or self.settings.GCS_BUCKET,
                object_key=object_key,
                method="GET",
                ttl_seconds=ttl_seconds,
            )

        expires_epoch = int((datetime.now(UTC) + timedelta(seconds=ttl_seconds)).timestamp())
        sig = self._local_signature("GET", object_key, expires_epoch, "")
        base = self.settings.PUBLIC_API_BASE_URL.rstrip("/")
        query = urlencode({"exp": expires_epoch, "sig": sig})
        return f"{base}/v1/media/local/{object_key}?{query}"

    def inspect_object(self, storage_uri: str, header_limit: int = 64) -> StoredObjectInfo:
        scheme, bucket, object_key = self.parse_storage_uri(storage_uri)
        if scheme == "gcs":
            client = self._get_gcs_client()
            blob = client.bucket(bucket or self.settings.GCS_BUCKET).blob(object_key)
            if not blob.exists():
                return StoredObjectInfo(
                    exists=False, byte_size=None, content_type=None, header_bytes=b""
                )
            blob.reload()
            size = blob.size if blob.size is not None else 0
            header = blob.download_as_bytes(start=0, end=max(0, min(size - 1, header_limit - 1)))
            return StoredObjectInfo(
                exists=True,
                byte_size=size,
                content_type=blob.content_type,
                header_bytes=bytes(header),
            )

        path = self.safe_local_path(object_key)
        if not path.is_file():
            return StoredObjectInfo(
                exists=False, byte_size=None, content_type=None, header_bytes=b""
            )
        size = path.stat().st_size
        with path.open("rb") as fh:
            header = fh.read(header_limit)
        ext = path.suffix.lower()
        return StoredObjectInfo(
            exists=True,
            byte_size=size,
            content_type=EXT_CONTENT_TYPE_MAP.get(ext),
            header_bytes=header,
        )

    def exists(self, storage_uri: str) -> bool:
        scheme, bucket, object_key = self.parse_storage_uri(storage_uri)
        if scheme == "gcs":
            client = self._get_gcs_client()
            blob = client.bucket(bucket or self.settings.GCS_BUCKET).blob(object_key)
            return bool(blob.exists())
        return self.safe_local_path(object_key).is_file()

    def read_bytes(self, storage_uri: str, max_bytes: int = 20_971_520) -> bytes:
        scheme, bucket, object_key = self.parse_storage_uri(storage_uri)
        if scheme == "gcs":
            client = self._get_gcs_client()
            blob = client.bucket(bucket or self.settings.GCS_BUCKET).blob(object_key)
            blob.reload()
            if blob.size is not None and blob.size > max_bytes:
                raise ValueError(f"Object exceeds maximum readable size ({max_bytes} bytes)")
            return bytes(blob.download_as_bytes())
        path = self.safe_local_path(object_key)
        if path.stat().st_size > max_bytes:
            raise ValueError(f"Object exceeds maximum readable size ({max_bytes} bytes)")
        return path.read_bytes()

    def write_local_bytes_exclusive(self, object_key: str, data: bytes) -> Path:
        """Write bytes atomically without overwriting any existing object."""
        path = self.safe_local_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Media object already exists: {object_key}")

        fd, tmp_name = tempfile.mkstemp(prefix=".upload-", dir=path.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            # Atomic hard-link + unlink prevents TOCTOU overwrite if supported; fall back safely
            try:
                os.link(tmp_path, path)
            except OSError:
                if path.exists():
                    raise FileExistsError(f"Media object already exists: {object_key}") from None
                os.replace(tmp_path, path)
            else:
                tmp_path.unlink(missing_ok=True)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return path

    def write_local_bytes(self, object_key: str, data: bytes) -> Path:
        """Backward-compatible wrapper enforcing write-once object immutability."""
        return self.write_local_bytes_exclusive(object_key, data)
