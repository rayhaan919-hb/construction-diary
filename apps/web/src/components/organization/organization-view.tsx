"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Building2,
  CreditCard,
  Download,
  History,
  MailPlus,
  PauseCircle,
  PlayCircle,
  ShieldAlert,
  Trash2,
  Users,
} from "lucide-react";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import type {
  AuditLogListResponse,
  BillingCheckoutResponse,
  Organization,
  OrganizationInvitation,
  OrganizationMember,
  OrganizationUsage,
  PlanTier,
  Role,
} from "@/lib/types";

interface OrganizationViewProps {
  initialOrg: Organization;
  initialUsage: OrganizationUsage;
  initialMembers: OrganizationMember[];
  initialInvitations: OrganizationInvitation[];
  initialAuditLogs: AuditLogListResponse;
  currentUserId: string;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${Math.round(bytes / 1024)} KB`;
}

function UsageBar({ label, used, max, formatted }: { label: string; used: number; max: number; formatted?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-[#0F172A]">{label}</span>
        <span className="font-mono text-[#64748B]">{formatted ?? `${used} / ${max}`}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-[#E2E8F0] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            pct >= 90 ? "bg-[#EF4444]" : pct >= 70 ? "bg-[#F59E0B]" : "bg-[#10B981]"
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function OrganizationView({
  initialOrg,
  initialUsage,
  initialMembers,
  initialInvitations,
  initialAuditLogs,
  currentUserId,
}: OrganizationViewProps) {
  const [org, setOrg] = useState<Organization>(initialOrg);
  const [usage, setUsage] = useState<OrganizationUsage>(initialUsage);
  const [members, setMembers] = useState<OrganizationMember[]>(initialMembers);
  const [invitations, setInvitations] = useState<OrganizationInvitation[]>(initialInvitations);
  const [auditLogs, setAuditLogs] = useState<AuditLogListResponse>(initialAuditLogs);

  const [orgName, setOrgName] = useState(initialOrg.name);
  const [orgSlug, setOrgSlug] = useState(initialOrg.slug);
  const [savingProfile, setSavingProfile] = useState(false);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("SUPERVISOR");
  const [inviting, setInviting] = useState(false);

  const [planBusy, setPlanBusy] = useState(false);
  const [billingMessage, setBillingMessage] = useState<string | null>(null);
  const [deleteSlugConfirm, setDeleteSlugConfirm] = useState("");
  const [exporting, setExporting] = useState(false);

  const [bannerError, setBannerError] = useState<string | null>(null);
  const [bannerInfo, setBannerInfo] = useState<string | null>(null);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setBannerError(null);
    setBannerInfo(null);
    setSavingProfile(true);
    try {
      const updated = await bffFetch<Organization>("/v1/organization", {
        method: "PATCH",
        body: JSON.stringify({ name: orgName.trim(), slug: orgSlug.trim() }),
      });
      setOrg(updated);
      setOrgName(updated.name);
      setOrgSlug(updated.slug);
      setBannerInfo("Company profile updated.");
    } catch (err) {
      setBannerError(getErrorMessage(err));
    } finally {
      setSavingProfile(false);
    }
  }

  async function switchPlan(tier: PlanTier) {
    setBannerError(null);
    setBannerInfo(null);
    setPlanBusy(true);
    try {
      const updated = await bffFetch<Organization>("/v1/organization/subscription", {
        method: "POST",
        body: JSON.stringify({ plan_tier: tier }),
      });
      setOrg(updated);
      const nextUsage = await bffFetch<OrganizationUsage>("/v1/organization/usage");
      setUsage(nextUsage);
      setBannerInfo(`Subscription updated to ${tier}.`);
    } catch (err) {
      setBannerError(getErrorMessage(err));
    } finally {
      setPlanBusy(false);
    }
  }

  async function launchCheckout(tier: PlanTier) {
    setBannerError(null);
    setBillingMessage(null);
    setPlanBusy(true);
    try {
      const res = await bffFetch<BillingCheckoutResponse>("/v1/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ plan_tier: tier }),
      });
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
        return;
      }
      setBillingMessage(res.message);
    } catch (err) {
      setBannerError(getErrorMessage(err));
    } finally {
      setPlanBusy(false);
    }
  }

  async function sendInvite(e: React.FormEvent) {
    e.preventDefault();
    setBannerError(null);
    setBannerInfo(null);
    setInviting(true);
    try {
      const created = await bffFetch<OrganizationInvitation>("/v1/organization/invitations", {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail.trim(),
          full_name: inviteName.trim(),
          role: inviteRole,
        }),
      });
      setInvitations((prev) => [created, ...prev]);
      setInviteEmail("");
      setInviteName("");
      setBannerInfo(
        created.invite_token
          ? `Invitation created. Invite token: ${created.invite_token}`
          : "Invitation sent."
      );
    } catch (err) {
      setBannerError(getErrorMessage(err));
    } finally {
      setInviting(false);
    }
  }

  async function revokeInvite(inviteId: string) {
    setBannerError(null);
    try {
      await bffFetch(`/v1/organization/invitations/${inviteId}`, { method: "DELETE" });
      setInvitations((prev) =>
        prev.map((inv) =>
          inv.id === inviteId ? { ...inv, revoked_at: new Date().toISOString() } : inv
        )
      );
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  async function changeMemberRole(userId: string, role: Role) {
    setBannerError(null);
    try {
      const updated = await bffFetch<OrganizationMember>(`/v1/organization/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      setMembers((prev) => prev.map((m) => (m.user_id === userId ? updated : m)));
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  async function removeMember(userId: string, name: string) {
    if (!window.confirm(`Remove ${name} from the organization?`)) return;
    setBannerError(null);
    try {
      await bffFetch(`/v1/organization/members/${userId}`, { method: "DELETE" });
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  async function loadMoreAuditLogs() {
    setBannerError(null);
    try {
      const next = await bffFetch<AuditLogListResponse>(
        `/v1/organization/audit-logs?limit=${auditLogs.limit}&offset=${auditLogs.items.length}`
      );
      setAuditLogs((prev) => ({
        ...next,
        items: [...prev.items, ...next.items],
      }));
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  async function downloadOrgExport() {
    setBannerError(null);
    setExporting(true);
    try {
      const payload = await bffFetch<unknown>("/v1/organization/export");
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${org.slug || "sitediary"}-export.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setBannerError(getErrorMessage(err));
    } finally {
      setExporting(false);
    }
  }

  async function toggleSuspension() {
    setBannerError(null);
    setBannerInfo(null);
    const suspending = org.status === "ACTIVE";
    const endpoint = suspending ? "/v1/organization/suspend" : "/v1/organization/unsuspend";
    if (
      suspending &&
      !window.confirm("Suspend this organization workspace? Supervisors will be blocked from syncing.")
    ) {
      return;
    }
    try {
      const updated = await bffFetch<Organization>(endpoint, { method: "POST" });
      setOrg(updated);
      setBannerInfo(suspending ? "Organization suspended." : "Organization reactivated.");
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  async function requestOrgDeletion(e: React.FormEvent) {
    e.preventDefault();
    setBannerError(null);
    setBannerInfo(null);
    try {
      await bffFetch("/v1/organization/delete", {
        method: "POST",
        body: JSON.stringify({ confirm_slug: deleteSlugConfirm.trim() }),
      });
      setDeleteSlugConfirm("");
      setBannerInfo("Organization deletion request queued for lifecycle purge.");
    } catch (err) {
      setBannerError(getErrorMessage(err));
    }
  }

  return (
    <main className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#0F172A]">
            Organization &amp; Billing Administration
          </h1>
          <p className="text-sm text-[#64748B]">
            Manage company profile, plan quotas, seat invitations, audit trail, and workspace lifecycle.
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-lg border border-[#E2E8F0] bg-white px-3.5 py-2 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC]"
        >
          ← Back to Portfolio
        </Link>
      </div>

      {bannerError ? (
        <div
          role="alert"
          className="rounded-xl border border-[#FECACA] bg-[#FEF2F2] px-4 py-3 text-sm text-[#B91C1C]"
        >
          {bannerError}
        </div>
      ) : null}

      {bannerInfo ? (
        <div className="rounded-xl border border-[#BBF7D0] bg-[#F0FDF4] px-4 py-3 text-sm text-[#166534]">
          {bannerInfo}
        </div>
      ) : null}

      {/* Top Grid: Profile & Usage */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-[#E2E8F0] bg-white p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="flex items-center gap-2 text-base font-semibold text-[#0F172A]">
              <Building2 className="h-4 w-4 text-[#E05D38]" />
              Company Profile
            </h2>
            <span
              className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                org.status === "ACTIVE"
                  ? "bg-[#ECFDF5] text-[#059669]"
                  : "bg-[#FEF2F2] text-[#B91C1C]"
              }`}
            >
              {org.status}
            </span>
          </div>

          <form onSubmit={saveProfile} className="space-y-4">
            <div>
              <label htmlFor="orgName" className="block text-xs font-medium text-[#475569]">
                Company Name
              </label>
              <input
                id="orgName"
                type="text"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-[#CBD5E1] px-3 py-2 text-sm text-[#0F172A]"
              />
            </div>

            <div>
              <label htmlFor="orgSlug" className="block text-xs font-medium text-[#475569]">
                Workspace Slug
              </label>
              <input
                id="orgSlug"
                type="text"
                required
                pattern="[a-z0-9-]+"
                value={orgSlug}
                onChange={(e) => setOrgSlug(e.target.value.toLowerCase())}
                className="mt-1 block w-full rounded-lg border border-[#CBD5E1] px-3 py-2 text-sm font-mono text-[#0F172A]"
              />
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="rounded-lg bg-[#0F172A] px-4 py-2 text-xs font-semibold text-white hover:bg-[#1E293B] disabled:opacity-50"
            >
              {savingProfile ? "Saving..." : "Save Company Profile"}
            </button>
          </form>
        </section>

        <section className="rounded-xl border border-[#E2E8F0] bg-white p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-base font-semibold text-[#0F172A]">
              <CreditCard className="h-4 w-4 text-[#E05D38]" />
              Plan &amp; Quota Usage ({org.plan_tier})
            </h2>
            <span className="text-xs font-medium text-[#64748B]">{org.subscription_status}</span>
          </div>

          <div className="space-y-3">
            <UsageBar label="Active Projects" used={usage.active_projects} max={usage.max_projects} />
            <UsageBar label="Active Seats" used={usage.active_seats} max={usage.max_seats} />
            <UsageBar
              label="Media Storage"
              used={usage.storage_bytes_used}
              max={usage.max_storage_bytes}
              formatted={`${formatBytes(usage.storage_bytes_used)} / ${formatBytes(usage.max_storage_bytes)}`}
            />
            <UsageBar
              label={`AI Extractions (${org.billing_month})`}
              used={usage.ai_extractions_this_month}
              max={usage.max_ai_extractions_monthly}
            />
          </div>

          <div className="pt-2 flex flex-wrap items-center gap-2">
            {(["FREE", "PRO", "ENTERPRISE"] as PlanTier[]).map((tier) => (
              <button
                key={tier}
                type="button"
                disabled={planBusy || org.plan_tier === tier}
                onClick={() => switchPlan(tier)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors ${
                  org.plan_tier === tier
                    ? "border-[#0F172A] bg-[#0F172A] text-white"
                    : "border-[#E2E8F0] bg-white text-[#0F172A] hover:bg-[#F8FAFC]"
                }`}
              >
                {tier}
              </button>
            ))}
            <button
              type="button"
              disabled={planBusy}
              onClick={() => launchCheckout("PRO")}
              className="ml-auto rounded-lg bg-[#E05D38] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#C94D2B] disabled:opacity-50"
            >
              Manage Stripe Billing
            </button>
          </div>
          {billingMessage ? (
            <p className="text-xs text-[#64748B] bg-[#F8FAFC] border border-[#E2E8F0] rounded-lg px-3 py-2">
              {billingMessage}
            </p>
          ) : null}
        </section>
      </div>

      {/* Team Members & Invitations */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-[#E2E8F0] bg-white p-6 space-y-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-[#0F172A]">
            <Users className="h-4 w-4 text-[#E05D38]" />
            Organization Members ({members.length})
          </h2>

          <div className="divide-y divide-[#F1F5F9]">
            {members.map((m) => (
              <div key={m.user_id} className="py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[#0F172A] truncate">{m.full_name}</p>
                  <p className="text-xs text-[#64748B] truncate">{m.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    aria-label={`Role for ${m.full_name}`}
                    value={m.role}
                    disabled={m.user_id === currentUserId}
                    onChange={(e) => changeMemberRole(m.user_id, e.target.value as Role)}
                    className="rounded-lg border border-[#CBD5E1] bg-white px-2.5 py-1 text-xs text-[#0F172A]"
                  >
                    <option value="OWNER">OWNER</option>
                    <option value="SUPERVISOR">SUPERVISOR</option>
                  </select>
                  {m.user_id !== currentUserId ? (
                    <button
                      type="button"
                      onClick={() => removeMember(m.user_id, m.full_name)}
                      className="rounded-lg border border-[#FECACA] px-2.5 py-1 text-xs font-medium text-[#B91C1C] hover:bg-[#FEF2F2]"
                    >
                      Remove
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-[#E2E8F0] bg-white p-6 space-y-4">
          <h2 className="flex items-center gap-2 text-base font-semibold text-[#0F172A]">
            <MailPlus className="h-4 w-4 text-[#E05D38]" />
            Workspace Invitations
          </h2>

          <form onSubmit={sendInvite} className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input
              type="text"
              required
              placeholder="Full name"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              className="rounded-lg border border-[#CBD5E1] px-3 py-2 text-xs text-[#0F172A]"
            />
            <input
              type="email"
              required
              placeholder="email@company.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              className="rounded-lg border border-[#CBD5E1] px-3 py-2 text-xs text-[#0F172A]"
            />
            <div className="flex gap-2">
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as Role)}
                className="rounded-lg border border-[#CBD5E1] bg-white px-2 py-2 text-xs text-[#0F172A]"
              >
                <option value="SUPERVISOR">SUPERVISOR</option>
                <option value="OWNER">OWNER</option>
              </select>
              <button
                type="submit"
                disabled={inviting}
                className="flex-1 rounded-lg bg-[#0F172A] px-3 py-2 text-xs font-semibold text-white hover:bg-[#1E293B] disabled:opacity-50"
              >
                {inviting ? "..." : "Invite"}
              </button>
            </div>
          </form>

          <div className="divide-y divide-[#F1F5F9]">
            {invitations.map((inv) => {
              const status = inv.accepted_at
                ? "ACCEPTED"
                : inv.revoked_at
                  ? "REVOKED"
                  : "PENDING";
              return (
                <div key={inv.id} className="py-2.5 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[#0F172A] truncate">
                      {inv.full_name} · <span className="text-xs font-normal text-[#64748B]">{inv.email}</span>
                    </p>
                    <p className="text-[11px] text-[#64748B]">
                      {inv.role} · {status}
                    </p>
                  </div>
                  {status === "PENDING" ? (
                    <button
                      type="button"
                      onClick={() => revokeInvite(inv.id)}
                      className="rounded-lg border border-[#FECACA] px-2.5 py-1 text-xs font-medium text-[#B91C1C] hover:bg-[#FEF2F2]"
                    >
                      Revoke
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Audit Trail */}
      <section className="rounded-xl border border-[#E2E8F0] bg-white p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-base font-semibold text-[#0F172A]">
            <History className="h-4 w-4 text-[#E05D38]" />
            Immutable Audit Log ({auditLogs.total})
          </h2>
          <button
            type="button"
            disabled={exporting}
            onClick={downloadOrgExport}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#E2E8F0] px-3 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC]"
          >
            <Download className="h-3.5 w-3.5" />
            {exporting ? "Exporting..." : "Export Organization JSON"}
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#E2E8F0] text-[#64748B]">
                <th className="py-2 pr-3 font-medium">#</th>
                <th className="py-2 pr-3 font-medium">Action</th>
                <th className="py-2 pr-3 font-medium">Actor</th>
                <th className="py-2 pr-3 font-medium">Resource</th>
                <th className="py-2 font-medium">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9]">
              {auditLogs.items.map((item) => (
                <tr key={item.id}>
                  <td className="py-2 pr-3 font-mono text-[#64748B]">{item.sequence_num}</td>
                  <td className="py-2 pr-3 font-semibold text-[#0F172A]">{item.action}</td>
                  <td className="py-2 pr-3 text-[#475569]">{item.actor_email ?? "system"}</td>
                  <td className="py-2 pr-3 font-mono text-[#64748B]">
                    {item.resource_type}
                    {item.resource_id ? `:${item.resource_id.slice(0, 8)}` : ""}
                  </td>
                  <td className="py-2 font-mono text-[#64748B]">
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {auditLogs.items.length < auditLogs.total ? (
          <button
            type="button"
            onClick={loadMoreAuditLogs}
            className="rounded-lg border border-[#E2E8F0] px-3.5 py-1.5 text-xs font-medium text-[#0F172A] hover:bg-[#F8FAFC]"
          >
            Load Older Audit Events
          </button>
        ) : null}
      </section>

      {/* Lifecycle Danger Zone */}
      <section className="rounded-xl border border-[#FECACA] bg-[#FEF2F2]/60 p-6 space-y-4">
        <h2 className="flex items-center gap-2 text-base font-semibold text-[#991B1B]">
          <ShieldAlert className="h-4 w-4" />
          Workspace Lifecycle &amp; Danger Zone
        </h2>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-[#0F172A]">
              {org.status === "ACTIVE" ? "Suspend Organization" : "Reactivate Organization"}
            </p>
            <p className="text-xs text-[#64748B]">
              Temporarily pause write access and sync without deleting historical site logs or permits.
            </p>
          </div>
          <button
            type="button"
            onClick={toggleSuspension}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#E2E8F0] bg-white px-3.5 py-2 text-xs font-semibold text-[#0F172A] hover:bg-[#F8FAFC]"
          >
            {org.status === "ACTIVE" ? (
              <>
                <PauseCircle className="h-4 w-4 text-[#D97706]" />
                Suspend Workspace
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4 text-[#10B981]" />
                Unsuspend Workspace
              </>
            )}
          </button>
        </div>

        <form onSubmit={requestOrgDeletion} className="pt-3 border-t border-[#FECACA] flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex-1">
            <p className="text-xs font-medium text-[#991B1B]">
              Delete Organization (type <code className="font-mono">{org.slug}</code> to confirm)
            </p>
          </div>
          <input
            type="text"
            required
            placeholder={org.slug}
            value={deleteSlugConfirm}
            onChange={(e) => setDeleteSlugConfirm(e.target.value)}
            className="rounded-lg border border-[#FCA5A5] bg-white px-3 py-1.5 text-xs font-mono text-[#0F172A]"
          />
          <button
            type="submit"
            disabled={deleteSlugConfirm.trim() !== org.slug}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#DC2626] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#B91C1C] disabled:opacity-40"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Request Deletion
          </button>
        </form>
      </section>
    </main>
  );
}
