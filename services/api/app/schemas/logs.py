from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.permits import PermitResponse

ExtractionStatus = Literal["NOT_STARTED", "PENDING", "PROCESSING", "DONE", "FAILED"]
AudioUploadStatus = Literal["NONE", "PENDING", "UPLOADED"]
PhotoUploadStatus = Literal["PENDING", "UPLOADED"]
DetectedLanguage = Literal["ur", "en", "ar", "mixed", "unknown"]
ExtractionTargetType = Literal["SITE_LOG", "SITE_LOG_PHOTO", "PERMIT"]
ExtractionJobStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELED"]


def _trim_string_list(values: list[str], *, max_items: int = 50, max_len: int = 300) -> list[str]:
    out: list[str] = []
    for raw in values[:max_items]:
        cleaned = str(raw).strip()
        if cleaned:
            out.append(cleaned[:max_len])
    return out


class StructuredSummary(BaseModel):
    tasks_completed: list[str] = Field(default_factory=list, max_length=50)
    labor_count: int | None = Field(default=None, ge=0, le=50_000)
    material_deliveries: list[str] = Field(default_factory=list, max_length=50)
    blockers: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tasks_completed", "material_deliveries", "blockers")
    @classmethod
    def sanitize_list_items(cls, value: list[str]) -> list[str]:
        return _trim_string_list(value)


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
    ai_caption: str | None = None
    ai_labels: dict[str, object] | None = None
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
    audio_url: str | None = None
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


class SiteLogPatchRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    transcript: str | None = Field(default=None, max_length=12000)
    structured_summary: StructuredSummary | None = None
    edited_by_human: bool | None = None


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
    log_id: UUID | None = None
    target_type: ExtractionTargetType = "SITE_LOG"
    target_id: UUID | None = None


class ExtractQueuedResponse(BaseModel):
    log_id: UUID
    extraction_status: ExtractionStatus
    job_id: UUID | None = None


class ExtractionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    target_type: ExtractionTargetType
    target_id: UUID
    status: ExtractionJobStatus
    attempts: int
    max_attempts: int
    next_run_at: datetime
    last_error: str | None = None
    model_name: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
