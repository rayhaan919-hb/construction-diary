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
export type SiteLog = components["schemas"]["SiteLog"];
export type SiteLogPhoto = components["schemas"]["SiteLogPhoto"];
export type DailyReport = components["schemas"]["DailyReport"];

export type MediaKind = components["schemas"]["MediaKind"];
export type UploadTicket = components["schemas"]["UploadTicket"];

export type TimelineResponse =
  paths["/v1/projects/{project_id}/timeline"]["get"]["responses"]["200"]["content"]["application/json"];

export type InviteMemberResponse =
  paths["/v1/projects/{project_id}/members"]["post"]["responses"]["201"]["content"]["application/json"];

export type ExtractQueueResponse =
  paths["/v1/logs/extract"]["post"]["responses"]["202"]["content"]["application/json"];
