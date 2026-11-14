from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PermitStatus = Literal["ACTIVE", "EXPIRING_SOON", "EXPIRED"]


class PermitInput(BaseModel):
    permit_name: str = Field(min_length=1, max_length=200)
    authority: str = Field(min_length=1, max_length=200)
    permit_number: str | None = Field(default=None, max_length=120)
    issue_date: date | None = None
    expiry_date: date
    document_photo_uri: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_dates(self) -> PermitInput:
        if self.issue_date is not None and self.issue_date > self.expiry_date:
            raise ValueError("issue_date must not be later than expiry_date")
        return self


class PermitPatch(BaseModel):
    permit_name: str | None = Field(default=None, min_length=1, max_length=200)
    authority: str | None = Field(default=None, min_length=1, max_length=200)
    permit_number: str | None = Field(default=None, max_length=120)
    issue_date: date | None = None
    expiry_date: date | None = None
    document_photo_uri: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_dates(self) -> PermitPatch:
        if (
            self.issue_date is not None
            and self.expiry_date is not None
            and self.issue_date > self.expiry_date
        ):
            raise ValueError("issue_date must not be later than expiry_date")
        return self


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
    document_upload_status: str = "NONE"
    ai_extracted_data: dict[str, Any] | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    server_version: int
