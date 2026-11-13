from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MediaKind = Literal["AUDIO", "PHOTO", "PERMIT_DOC"]
MediaContentType = Literal["audio/mp4", "image/jpeg"]


class UploadUrlRequest(BaseModel):
    kind: MediaKind
    project_id: UUID
    object_id: UUID
    content_type: MediaContentType
    byte_size: int = Field(ge=1, le=20_971_520)


class UploadTicketResponse(BaseModel):
    upload_url: str
    method: Literal["PUT"] = "PUT"
    headers: dict[str, str]
    storage_uri: str
    expires_at: datetime


class MediaCompleteRequest(BaseModel):
    kind: MediaKind
    object_id: UUID
