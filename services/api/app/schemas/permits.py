from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PermitStatus = Literal["ACTIVE", "EXPIRING_SOON", "EXPIRED"]


class PermitInput(BaseModel):
    permit_name: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    permit_number: str | None = None
    issue_date: date | None = None
    expiry_date: date
    document_photo_uri: str | None = None


class PermitPatch(BaseModel):
    permit_name: str | None = Field(default=None, min_length=1)
    authority: str | None = Field(default=None, min_length=1)
    permit_number: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    document_photo_uri: str | None = None


class PermitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    permit_name: str
    authority: str
    permit_number: str | None = None
    issue_date: date | None = None
    expiry_date: date
    status: PermitStatus
    days_to_expiry: int
    document_photo_uri: str | None = None
    document_photo_url: str | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    server_version: int
