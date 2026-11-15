import type { components, paths } from "./api-types";

export type Problem = components["schemas"]["Problem"];
export type Role = components["schemas"]["Role"];
export type User = components["schemas"]["User"];
export type TokenPair = components["schemas"]["TokenPair"];

export type Project = components["schemas"]["Project"];
export type ProjectInput = components["schemas"]["ProjectInput"];
export type ProjectPatch = components["schemas"]["ProjectPatch"];
export type ProjectSummary = components["schemas"]["ProjectSummary"];

export type PermitHealth = components["schemas"]["PermitHealth"];
export type PermitStatus = components["schemas"]["PermitStatus"];
export type Permit = components["schemas"]["Permit"];
export type PermitInput = components["schemas"]["PermitInput"];
export type PermitPatch = components["schemas"]["PermitPatch"];

export type Member = components["schemas"]["Member"];

export type ExtractionStatus = components["schemas"]["ExtractionStatus"];
export type StructuredSummary = components["schemas"]["StructuredSummary"];
export type SiteLog = components["schemas"]["SiteLog"] & {
  audio_url?: string | null;
};
export type SiteLogPhoto = components["schemas"]["SiteLogPhoto"];
export type DailyReport = components["schemas"]["DailyReport"];

export type MediaKind = components["schemas"]["MediaKind"];
export type UploadTicket = components["schemas"]["UploadTicket"] & {
  ticket_id?: string | null;
};

export type PlanTier = "FREE" | "STARTER" | "PRO" | "ENTERPRISE";
export type OrgStatus = "ACTIVE" | "SUSPENDED" | "PENDING_DELETION";
export type SubscriptionStatus = "TRIALING" | "ACTIVE" | "PAST_DUE" | "CANCELED";

export interface Organization {
  id: string;
  name: string;
  slug: string;
  status: OrgStatus;
  plan_tier: PlanTier;
  subscription_status: SubscriptionStatus;
  billing_provider: string;
  trial_ends_at: string | null;
  current_period_end: string | null;
  max_projects: number;
  max_seats: number;
  max_storage_bytes: number;
  max_ai_extractions_monthly: number;
  ai_extractions_this_month: number;
  storage_bytes_used: number;
  billing_month: string;
  created_at: string;
  updated_at: string;
}

export interface OrganizationUsage {
  organization_id: string;
  active_projects: number;
  max_projects: number;
  active_seats: number;
  max_seats: number;
  storage_bytes_used: number;
  max_storage_bytes: number;
  ai_extractions_this_month: number;
  max_ai_extractions_monthly: number;
}

export interface OrganizationMember {
  organization_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  status: string;
  created_at: string;
}

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  project_id: string | null;
  email: string;
  full_name: string;
  role: Role;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  invite_token?: string | null;
}

export interface AuditLogItem {
  id: string;
  sequence_num: number;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BillingCheckoutResponse {
  provider: string;
  configured: boolean;
  checkout_url: string | null;
  message: string;
}

export type TimelineResponse =
  paths["/v1/projects/{project_id}/timeline"]["get"]["responses"]["200"]["content"]["application/json"];

export type InviteMemberResponse =
  paths["/v1/projects/{project_id}/members"]["post"]["responses"]["201"]["content"]["application/json"];

export type ExtractQueueResponse =
  paths["/v1/logs/extract"]["post"]["responses"]["202"]["content"]["application/json"];
