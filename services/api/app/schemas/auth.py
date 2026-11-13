from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["OWNER", "SUPERVISOR"]
Locale = Literal["en", "ur", "ar"]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: Role
    preferred_locale: Locale
    must_change_password: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    device_label: str | None = Field(default=None, max_length=120)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_at: datetime
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class DeviceTokenRequest(BaseModel):
    fcm_token: str = Field(min_length=1)
