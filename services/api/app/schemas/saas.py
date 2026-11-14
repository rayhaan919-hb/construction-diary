from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.permissions import Role
from app.schemas.auth import Locale, TokenPairResponse, UserResponse

PlanTier = Literal["FREE", "STARTER", "PRO", "ENTERPRISE"]
OrgStatus = Literal["ACTIVE", "SUSPENDED", "PENDING_DELETION"]
SubscriptionStatus = Literal["TRIALING", "ACTIVE", "PAST_DUE", "CANCELED"]


class OrganizationRegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    company_slug: str | None = Field(default=None, min_length=2, max_length=80)
    owner_email: EmailStr
    owner_full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=512)
    preferred_locale: Locale = "en"
    plan_tier: PlanTier = "STARTER"


class OrganizationRegisterResponse(BaseModel):
    organization: OrganizationResponse
    user: UserResponse
    tokens: TokenPairResponse


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    status: OrgStatus
    plan_tier: PlanTier
    subscription_status: SubscriptionStatus
    billing_provider: str
    billing_customer_id: str | None = None
    billing_subscription_id: str | None = None
    trial_ends_at: datetime | None = None
    current_period_end: datetime | None = None
    max_projects: int
    max_seats: int
    max_storage_bytes: int
    max_ai_extractions_monthly: int
    ai_extractions_this_month: int
    storage_bytes_used: int
    billing_month: str
    created_at: datetime
    updated_at: datetime


class OrganizationUsageResponse(BaseModel):
    organization_id: UUID
    active_projects: int
    max_projects: int
    active_seats: int
    max_seats: int
    storage_bytes_used: int
    max_storage_bytes: int
    ai_extractions_this_month: int
    max_ai_extractions_monthly: int


class OrganizationPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)


class OrganizationMemberResponse(BaseModel):
    organization_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: Role
    status: str
    created_at: datetime


class OrganizationMemberRoleUpdateRequest(BaseModel):
    role: Role


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: Role = "SUPERVISOR"
    project_id: UUID | None = None


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    email: str
    full_name: str
    role: Role
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    invite_token: str | None = None


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    password: str = Field(min_length=8, max_length=512)


class SubscriptionPlanChangeRequest(BaseModel):
    plan_tier: PlanTier


class BillingCheckoutResponse(BaseModel):
    provider: str
    configured: bool
    checkout_url: str | None = None
    message: str


class AuditLogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence_num: int
    organization_id: UUID | None = None
    actor_user_id: UUID | None = None
    actor_email: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
    details: dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItemResponse]
    total: int
    limit: int
    offset: int


class AccountDeleteRequest(BaseModel):
    confirm_slug: str = Field(min_length=1, max_length=80)
