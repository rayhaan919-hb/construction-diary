from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.permissions import Role

Locale = Literal["en", "ur", "ar"]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None = None
    email: str
    full_name: str
    role: Role
    status: str = "ACTIVE"
    preferred_locale: Locale
    must_change_password: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)
    device_label: str | None = Field(default=None, max_length=120)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_at: datetime
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)
    fcm_token: str | None = Field(default=None, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=512)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetRequestResponse(BaseModel):
    accepted: bool = True
    message: str
    # Non-null ONLY in local development/test when SMTP delivery is disabled
    dev_reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=512)


class ProfilePatchRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_locale: Locale | None = None


class SessionResponse(BaseModel):
    id: UUID
    device_label: str | None = None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class DeviceTokenRequest(BaseModel):
    fcm_token: str = Field(min_length=1, max_length=1024)
    platform: str = Field(default="ANDROID", max_length=16)

    @field_validator("platform")
    @classmethod
    def _validate_platform(cls, value: str) -> Literal["ANDROID"]:
        normalized = value.strip().upper()
        if normalized != "ANDROID":
            raise ValueError("Unsupported push notification platform; only ANDROID is supported")
        return "ANDROID"
