from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.permits import PermitResponse

ExtractionStatus = Literal["NOT_STARTED", "PENDING", "PROCESSING", "DONE", "FAILED"]
AudioUploadStatus = Literal["NONE", "PENDING", "UPLOADED"]
PhotoUploadStatus = Literal["PENDING", "UPLOADED"]
DetectedLanguage = Literal["ur", "en", "ar", "mixed", "unknown"]


class StructuredSummary(BaseModel):
    tasks_completed: list[str] = Field(default_factory=list)
    labor_count: int | None = Field(default=None, ge=0)
    material_deliveries: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class SiteLogPhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    site_log_id: UUID
    storage_uri: str
    upload_status: PhotoUploadStatus
    url: str | None = None
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    taken_at: datetime | None = None
    sort_order: int
    deleted_at: datetime | None = None
    server_version: int


class SiteLogBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    author_id: UUID
    author_name: str | None = None
    log_date: date
    recorded_at: datetime
    notes: str | None = None
    audio_uri: str | None = None
    audio_duration_ms: int | None = None
    audio_upload_status: AudioUploadStatus
    extraction_status: ExtractionStatus
    extraction_attempts: int
    extraction_error: str | None = None
    extraction_model: str | None = None
    extracted_at: datetime | None = None
    transcript: str | None = None
    detected_language: DetectedLanguage | None = None
    structured_summary: StructuredSummary | None = None
    edited_by_human: bool
    client_updated_at: datetime
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    server_version: int


class SiteLogPullResponse(SiteLogBase):
    """SiteLog representation for /v1/sync/pull (photos omitted)."""


class SiteLogResponse(SiteLogBase):
    """SiteLog representation for REST read endpoints (photos included)."""

    photos: list[SiteLogPhotoResponse] = Field(default_factory=list)


class DailyReportResponse(BaseModel):
    project_id: UUID
    project_name: str
    log_date: date
    labor_max: int | None
    log_count: int
    pending_extraction_count: int
    tasks_completed: list[str]
    material_deliveries: list[str]
    blockers: list[str]
    logs: list[SiteLogResponse]
    permits: list[PermitResponse]


class TimelineResponse(BaseModel):
    days: list[DailyReportResponse]
    next_before: date | None


class ExtractRequest(BaseModel):
    log_id: UUID


class ExtractQueuedResponse(BaseModel):
    log_id: UUID
    extraction_status: ExtractionStatus
