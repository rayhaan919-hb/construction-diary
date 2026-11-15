import React from "react";
import { redirect } from "next/navigation";
import { PortalHeader } from "@/components/layout/portal-header";
import { OrganizationView } from "@/components/organization/organization-view";
import { ApiError } from "@/lib/problem";
import { serverApiFetch } from "@/lib/server-api";
import type {
  AuditLogListResponse,
  Organization,
  OrganizationInvitation,
  OrganizationMember,
  OrganizationUsage,
  User,
} from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function OrganizationPage() {
  let user: User | null = null;
  try {
    user = await serverApiFetch<User>("/v1/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      redirect("/login");
    }
    throw err;
  }

  if (user.must_change_password) {
    redirect("/change-password");
  }

  if (user.role !== "OWNER") {
    redirect("/");
  }

  const [org, usage, members, invitations, auditLogs] = await Promise.all([
    serverApiFetch<Organization>("/v1/organization"),
    serverApiFetch<OrganizationUsage>("/v1/organization/usage"),
    serverApiFetch<OrganizationMember[]>("/v1/organization/members"),
    serverApiFetch<OrganizationInvitation[]>("/v1/organization/invitations"),
    serverApiFetch<AuditLogListResponse>("/v1/organization/audit-logs?limit=25&offset=0"),
  ]);

  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col">
      <PortalHeader user={user} />
      <OrganizationView
        initialOrg={org}
        initialUsage={usage}
        initialMembers={members}
        initialInvitations={invitations}
        initialAuditLogs={auditLogs}
        currentUserId={user.id}
      />
    </div>
  );
}
