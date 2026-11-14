from __future__ import annotations

import hashlib
import posixpath
from pathlib import PurePosixPath
from urllib.parse import unquote
from uuid import UUID

MAX_UPLOAD_BYTES = 20_971_520

KIND_CONTENT_TYPES: dict[str, dict[str, str]] = {
    "AUDIO": {
        "audio/mp4": ".m4a",
    },
    "PHOTO": {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    },
    "PERMIT_DOC": {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "application/pdf": ".pdf",
    },
}

_KIND_DIRS: dict[str, str] = {
    "AUDIO": "audio",
    "PHOTO": "photos",
    "PERMIT_DOC": "permits",
}

_DISALLOWED_ACTIVE_SIGNATURES = (
    b"<!doctype",
    b"<html",
    b"<svg",
    b"<script",
    b"mz",  # PE/DLL
    b"\x7felf",  # ELF
    b"#!",  # script shebang
)


def resolve_extension_for_kind(kind: str, content_type: str) -> str | None:
    allowed = KIND_CONTENT_TYPES.get(kind)
    if allowed is None:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return allowed.get(normalized)


def sanitize_relative_object_key(raw_key: str) -> str | None:
    """Validate and normalize an object key, rejecting path traversal or control chars."""
    decoded = unquote(raw_key)
    if (
        not raw_key
        or "\\" in raw_key
        or "\\" in decoded
        or "\x00" in raw_key
        or "\x00" in decoded
        or "?" in raw_key
        or "#" in raw_key
    ):
        return None

    parts = PurePosixPath(decoded).parts
    if any(part in ("..", ".", "/") for part in parts):
        return None

    normalized = posixpath.normpath(decoded.lstrip("/"))
    if (
        not normalized
        or normalized.startswith(".")
        or normalized.startswith("/")
        or normalized != decoded.lstrip("/")
    ):
        return None
    return normalized


def build_immutable_object_key(
    project_id: UUID | str,
    kind: str,
    object_id: UUID | str,
    ticket_id: UUID | str,
    content_type: str,
) -> str:
    kind_dir = _KIND_DIRS.get(kind)
    ext = resolve_extension_for_kind(kind, content_type)
    if kind_dir is None or ext is None:
        raise ValueError(f"Unsupported media kind/content_type: {kind}/{content_type}")
    return f"projects/{project_id}/{kind_dir}/{object_id}/{ticket_id}{ext}"


def validate_magic_bytes(content_type: str, header_bytes: bytes) -> bool:
    """Verify binary signature matches the declared MIME type and contains no active content."""
    if len(header_bytes) < 4:
        return False
    lower_prefix = header_bytes[:128].lstrip().lower()
    for bad in _DISALLOWED_ACTIVE_SIGNATURES:
        if lower_prefix.startswith(bad):
            return False

    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized == "image/jpeg":
        return len(header_bytes) >= 3 and header_bytes[:3] == b"\xff\xd8\xff"
    if normalized == "image/png":
        return len(header_bytes) >= 8 and header_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    if normalized == "image/webp":
        return (
            len(header_bytes) >= 12
            and header_bytes[:4] == b"RIFF"
            and header_bytes[8:12] == b"WEBP"
        )
    if normalized == "application/pdf":
        return len(header_bytes) >= 5 and header_bytes[:5] == b"%PDF-"
    if normalized == "audio/mp4":
        return len(header_bytes) >= 12 and header_bytes[4:8] == b"ftyp"
    return False


def validate_project_storage_uri(
    uri: str | None,
    *,
    project_id: UUID,
    storage_backend: str,
    gcs_bucket: str,
    expected_subdir: str | None = None,
) -> tuple[bool, str | None]:
    """Validate that a client-supplied storage URI stays strictly inside project boundaries."""
    if uri is None:
        return True, None

    if len(uri) > 512 or any(ch.isspace() for ch in uri):
        return False, "Invalid storage URI format"

    required_prefix = f"projects/{project_id}/"
    if expected_subdir:
        required_prefix = f"projects/{project_id}/{expected_subdir}/"

    if storage_backend == "local":
        if not uri.startswith("local://"):
            return False, "Storage URI scheme must match local backend"
        key = uri[len("local://") :]
    elif storage_backend == "gcs":
        expected_gs_prefix = f"gs://{gcs_bucket}/"
        if not gcs_bucket or not uri.startswith(expected_gs_prefix):
            return False, "Storage URI bucket is not authorized"
        key = uri[len(expected_gs_prefix) :]
    else:
        return False, "Unsupported storage backend"

    clean_key = sanitize_relative_object_key(key)
    if clean_key is None or clean_key != key:
        return False, "Storage URI contains invalid path segments"
    if not clean_key.startswith(required_prefix):
        return False, "Storage URI does not belong to target project"
    return True, None


def compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
