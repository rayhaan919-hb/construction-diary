from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import Role
from app.schemas.permits import PermitResponse

PermitHealth = Literal["OK", "WARN", "EXPIRED", "NONE"]


def _validate_iana_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid IANA timezone: {value}") from exc
    return value


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    site_address: str = Field(min_length=1)
    owner_phone: str | None = None
    timezone: str = "Asia/Karachi"
    allow_photo_gps: bool = False

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return _validate_iana_timezone(value)


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    site_address: str | None = Field(default=None, min_length=1)
    owner_phone: str | None = None
    timezone: str | None = None
    allow_photo_gps: bool | None = None

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_iana_timezone(value)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    site_address: str
    owner_phone: str | None = None
    timezone: str
    allow_photo_gps: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    server_version: int


class ProjectTodayStats(BaseModel):
    log_date: date
    labor_max: int | None
    log_count: int
    last_log_at: datetime | None = None


class ProjectSummaryResponse(BaseModel):
    project: ProjectResponse
    today: ProjectTodayStats
    permit_health: PermitHealth
    next_expiring_permit: PermitResponse | None = None
    open_blockers_count: int


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    user_id: UUID
    role: Role
    full_name: str
    email: str
    deleted_at: datetime | None = None
    server_version: int


class InviteMemberRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1)


class InviteMemberResponse(BaseModel):
    member: MemberResponse
    temporary_password: str | None = None
