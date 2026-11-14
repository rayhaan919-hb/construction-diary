from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.logs import SiteLogPhotoResponse, SiteLogPullResponse, StructuredSummary
from app.schemas.permits import PermitResponse
from app.schemas.projects import MemberResponse, ProjectResponse


class PermitPush(BaseModel):
    id: UUID
    project_id: UUID
    permit_name: str = Field(min_length=1, max_length=200)
    authority: str = Field(min_length=1, max_length=200)
    permit_number: str | None = Field(default=None, max_length=120)
    issue_date: date | None = None
    expiry_date: date
    document_photo_uri: str | None = Field(default=None, max_length=512)
    deleted_at: datetime | None = None
    client_updated_at: datetime

    @model_validator(mode="after")
    def validate_dates(self) -> PermitPush:
        if self.issue_date is not None and self.issue_date > self.expiry_date:
            raise ValueError("issue_date must not be later than expiry_date")
        return self


class SiteLogPush(BaseModel):
    id: UUID
    project_id: UUID
    log_date: date
    recorded_at: datetime
    notes: str | None = Field(default=None, max_length=4000)
    audio_uri: str | None = Field(default=None, max_length=512)
    audio_duration_ms: int | None = Field(default=None, ge=0, le=300_000)
    structured_summary: StructuredSummary | None = None
    edited_by_human: bool = False
    deleted_at: datetime | None = None
    client_updated_at: datetime


class SiteLogPhotoPush(BaseModel):
    id: UUID
    site_log_id: UUID
    storage_uri: str = Field(min_length=1, max_length=512)
    width: int | None = Field(default=None, ge=1, le=20_000)
    height: int | None = Field(default=None, ge=1, le=20_000)
    byte_size: int | None = Field(default=None, ge=1, le=20_971_520)
    taken_at: datetime | None = None
    sort_order: int = Field(default=0, ge=0, le=1000)
    deleted_at: datetime | None = None


class SyncPushChanges(BaseModel):
    permits: list[dict[str, Any]] = Field(default_factory=list)
    site_logs: list[dict[str, Any]] = Field(default_factory=list)
    site_log_photos: list[dict[str, Any]] = Field(default_factory=list)


class SyncPushRequest(BaseModel):
    changes: SyncPushChanges


class SyncPushResultItem(BaseModel):
    entity: Literal["permits", "site_logs", "site_log_photos"]
    id: UUID
    status: Literal["APPLIED", "REJECTED"]
    server_version: int | None = None
    error_code: str | None = None
    error_detail: str | None = None


class SyncPushResponse(BaseModel):
    server_time: datetime
    results: list[SyncPushResultItem]


class SyncPullChanges(BaseModel):
    projects: list[ProjectResponse]
    project_members: list[MemberResponse]
    permits: list[PermitResponse]
    site_logs: list[SiteLogPullResponse]
    site_log_photos: list[SiteLogPhotoResponse]


class SyncPullResponse(BaseModel):
    next_cursor: int
    has_more: bool
    changes: SyncPullChanges
