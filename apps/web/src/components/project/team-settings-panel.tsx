"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Check,
  Copy,
  KeyRound,
  Settings,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import type {
  InviteMemberResponse,
  Member,
  Project,
  ProjectPatch,
  User,
} from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import {
  EmptyState,
  InlineErrorBanner,
  SkeletonBlock,
} from "@/components/ui/states";

interface TeamSettingsPanelProps {
  project: Project;
  currentUser: User | null;
  members: Member[] | null;
  membersLoading: boolean;
  membersError: string | null;
  onRetryMembers: () => void;
  onMembersChange: (members: Member[]) => void;
  onProjectUpdated: (project: Project) => void;
}

export function TeamSettingsPanel({
  project,
  currentUser,
  members,
  membersLoading,
  membersError,
  onRetryMembers,
  onMembersChange,
  onProjectUpdated,
}: TeamSettingsPanelProps) {
  const router = useRouter();
  const isOwner = currentUser?.role === "OWNER";

  // Invite supervisor state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [tempPasswordAlert, setTempPasswordAlert] = useState<{
    email: string;
    password: string;
  } | null>(null);
  const [copiedPwd, setCopiedPwd] = useState(false);

  // Remove member state
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  // Project patch state
  const [projName, setProjName] = useState(project.name);
  const [projAddress, setProjAddress] = useState(project.site_address);
  const [projPhone, setProjPhone] = useState(project.owner_phone ?? "");
  const [projTimezone, setProjTimezone] = useState(project.timezone);
  const [projGps, setProjGps] = useState(project.allow_photo_gps);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsSaved, setSettingsSaved] = useState(false);

  // Delete project state
  const [confirmDeleteText, setConfirmDeleteText] = useState("");
  const [deletingProject, setDeletingProject] = useState(false);
  const [deleteProjectError, setDeleteProjectError] = useState<string | null>(
    null
  );

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setTempPasswordAlert(null);
    setCopiedPwd(false);
    setInviting(true);

    try {
      const resp = await bffFetch<InviteMemberResponse>(
        `/v1/projects/${project.id}/members`,
        {
          method: "POST",
          body: JSON.stringify({
            email: inviteEmail.trim(),
            full_name: inviteName.trim(),
          }),
        }
      );

      const currentList = members ?? [];
      const exists = currentList.some((m) => m.user_id === resp.member.user_id);
      const nextList = exists
        ? currentList.map((m) =>
            m.user_id === resp.member.user_id ? resp.member : m
          )
        : [...currentList, resp.member];
      onMembersChange(nextList);

      if (resp.temporary_password) {
        setTempPasswordAlert({
          email: resp.member.email,
          password: resp.temporary_password,
        });
      }
      setInviteEmail("");
      setInviteName("");
    } catch (err) {
      setInviteError(getErrorMessage(err, "Failed to invite supervisor"));
    } finally {
      setInviting(false);
    }
  }

  async function handleCopyTempPassword() {
    if (!tempPasswordAlert) return;
    try {
      await navigator.clipboard.writeText(tempPasswordAlert.password);
      setCopiedPwd(true);
      setTimeout(() => setCopiedPwd(false), 2000);
    } catch {
      // Clipboard fallback ignored cleanly
    }
  }

  async function handleRemoveMember(userId: string) {
    setRemoveError(null);
    setRemovingId(userId);
    try {
      await bffFetch<void>(`/v1/projects/${project.id}/members/${userId}`, {
        method: "DELETE",
      });
      onMembersChange((members ?? []).filter((m) => m.user_id !== userId));
      setConfirmRemoveId(null);
    } catch (err) {
      setRemoveError(getErrorMessage(err, "Failed to remove member"));
    } finally {
      setRemovingId(null);
    }
  }

  async function handleSaveProject(e: React.FormEvent) {
    e.preventDefault();
    setSettingsError(null);
    setSettingsSaved(false);
    setSavingSettings(true);

    const patch: ProjectPatch = {
      name: projName.trim(),
      site_address: projAddress.trim(),
      owner_phone: projPhone.trim() ? projPhone.trim() : null,
      timezone: projTimezone.trim(),
      allow_photo_gps: projGps,
    };

    try {
      const updated = await bffFetch<Project>(`/v1/projects/${project.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      onProjectUpdated(updated);
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
    } catch (err) {
      setSettingsError(getErrorMessage(err, "Failed to update project"));
    } finally {
      setSavingSettings(false);
    }
  }

  async function handleDeleteProject() {
    setDeleteProjectError(null);
    setDeletingProject(true);
    try {
      await bffFetch<void>(`/v1/projects/${project.id}`, {
        method: "DELETE",
      });
      router.replace("/");
      router.refresh();
    } catch (err) {
      setDeleteProjectError(getErrorMessage(err, "Failed to delete project"));
      setDeletingProject(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left 7 cols: Team Members & Supervisor Invite */}
      <div className="lg:col-span-7 space-y-6">
        {isOwner && (
          <section className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 sm:p-6 space-y-4">
            <div className="flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
              <h2 className="text-base font-semibold text-[#0F172A]">
                Invite Site Supervisor
              </h2>
            </div>
            <p className="text-xs text-[#475569]">
              Creates a new SUPERVISOR account (with a one-time temporary password) or adds an existing user to this project.
            </p>

            {inviteError && (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-md border border-[#FECACA] bg-[#FEF2F2] p-3 text-sm text-[#991B1B]"
              >
                <AlertCircle className="h-4 w-4 shrink-0 text-[#DC2626] mt-0.5" />
                <span>{inviteError}</span>
              </div>
            )}

            {tempPasswordAlert && (
              <div
                role="status"
                className="rounded-md border border-[#F59E0B] bg-[#FFFBEB] p-4 space-y-2"
              >
                <div className="flex items-center gap-2 text-sm font-semibold text-[#92400E]">
                  <KeyRound className="h-4 w-4 text-[#D97706]" />
                  <span>One-Time Temporary Password Generated</span>
                </div>
                <p className="text-xs text-[#78350F]">
                  Share these credentials securely with{" "}
                  <strong className="font-mono">{tempPasswordAlert.email}</strong>. This password will not be shown again; they will be prompted to change it on first login.
                </p>
                <div className="flex items-center justify-between gap-2 rounded border border-[#FDE68A] bg-[#FFFFFF] px-3 py-2">
                  <code className="font-mono text-sm font-bold text-[#0F172A] select-all">
                    {tempPasswordAlert.password}
                  </code>
                  <button
                    type="button"
                    onClick={handleCopyTempPassword}
                    className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-xs font-medium text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
                  >
                    {copiedPwd ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-[#059669]" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            <form
              onSubmit={handleInvite}
              className="grid grid-cols-1 sm:grid-cols-2 gap-3"
            >
              <div className="space-y-1">
                <label
                  htmlFor="invite-name"
                  className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
                >
                  Full Name
                </label>
                <input
                  id="invite-name"
                  type="text"
                  required
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="Tariq Mahmood"
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label
                  htmlFor="invite-email"
                  className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
                >
                  Email Address
                </label>
                <input
                  id="invite-email"
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="tariq@example.com"
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
                />
              </div>

              <div className="sm:col-span-2 flex justify-end pt-1">
                <button
                  type="submit"
                  disabled={inviting}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
                >
                  <UserPlus className="h-4 w-4" aria-hidden="true" />
                  <span>{inviting ? "Inviting..." : "Add Supervisor"}</span>
                </button>
              </div>
            </form>
          </section>
        )}

        <section className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] px-4 py-3 sm:px-6">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-[#0F172A]">
                Project Members
              </h2>
            </div>
            {members && (
              <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
                {members.length}
              </span>
            )}
          </div>

          <div className="p-4 sm:p-6 space-y-3">
            {removeError && (
              <InlineErrorBanner
                title="Could not remove member"
                message={removeError}
              />
            )}

            {membersLoading ? (
              <div className="space-y-2" aria-busy="true">
                {[0, 1, 2].map((i) => (
                  <SkeletonBlock key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : membersError ? (
              <InlineErrorBanner
                title="Failed to load project members"
                message={membersError}
                onRetry={onRetryMembers}
              />
            ) : !members || members.length === 0 ? (
              <EmptyState
                compact
                icon={<Users className="h-5 w-5" />}
                title="No project members found"
                description="Invite supervisors to capture offline site logs and photos."
              />
            ) : (
              <div className="divide-y divide-[#E2E8F0] rounded-md border border-[#E2E8F0]">
                {members.map((member) => {
                  const isSelf = currentUser?.id === member.user_id;
                  return (
                    <div
                      key={member.user_id}
                      className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-[#0F172A]">
                            {member.full_name}
                          </span>
                          <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#475569]">
                            {member.role}
                          </span>
                          {isSelf && (
                            <span className="font-mono text-[10px] text-[#64748B]">
                              (you)
                            </span>
                          )}
                        </div>
                        <p className="truncate font-mono text-xs text-[#475569]">
                          {member.email}
                        </p>
                      </div>

                      {isOwner && !isSelf && (
                        <div className="flex items-center gap-1.5 shrink-0">
                          {confirmRemoveId === member.user_id ? (
                            <>
                              <button
                                type="button"
                                disabled={removingId === member.user_id}
                                onClick={() => handleRemoveMember(member.user_id)}
                                className="rounded border border-[#FECACA] bg-[#DC2626] px-2.5 py-1 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B91C1C] disabled:opacity-50 cursor-pointer"
                              >
                                {removingId === member.user_id
                                  ? "Removing..."
                                  : "Confirm"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmRemoveId(null)}
                                className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-xs text-[#475569] hover:bg-[#F8FAFC] cursor-pointer"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmRemoveId(member.user_id)}
                              className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-xs font-medium text-[#475569] hover:border-[#FECACA] hover:bg-[#FEF2F2] hover:text-[#DC2626] cursor-pointer"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                              <span>Remove</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Right 5 cols: Project Settings & Delete */}
      <div className="lg:col-span-5 space-y-6">
        <section className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 sm:p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[#0F172A]">
              Project Settings
            </h2>
          </div>

          {settingsError && (
            <InlineErrorBanner
              title="Failed to save settings"
              message={settingsError}
            />
          )}

          {settingsSaved && (
            <div
              role="status"
              className="rounded-md border border-[#A7F3D0] bg-[#ECFDF5] px-3 py-2 text-xs font-medium text-[#065F46]"
            >
              Project details updated.
            </div>
          )}

          <form onSubmit={handleSaveProject} className="space-y-4">
            <div className="space-y-1">
              <label
                htmlFor="edit-proj-name"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Project Name
              </label>
              <input
                id="edit-proj-name"
                type="text"
                required
                disabled={!isOwner}
                maxLength={200}
                value={projName}
                onChange={(e) => setProjName(e.target.value)}
                className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] disabled:bg-[#F8FAFC] focus:border-[#D97706] focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="edit-proj-address"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Site Address
              </label>
              <textarea
                id="edit-proj-address"
                rows={2}
                required
                disabled={!isOwner}
                value={projAddress}
                onChange={(e) => setProjAddress(e.target.value)}
                className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] disabled:bg-[#F8FAFC] focus:border-[#D97706] focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="edit-proj-tz"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Timezone (IANA)
              </label>
              <input
                id="edit-proj-tz"
                type="text"
                required
                disabled={!isOwner}
                value={projTimezone}
                onChange={(e) => setProjTimezone(e.target.value)}
                className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm text-[#0F172A] disabled:bg-[#F8FAFC] focus:border-[#D97706] focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label
                htmlFor="edit-proj-phone"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Owner Phone
              </label>
              <input
                id="edit-proj-phone"
                type="tel"
                disabled={!isOwner}
                value={projPhone}
                onChange={(e) => setProjPhone(e.target.value)}
                className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm text-[#0F172A] disabled:bg-[#F8FAFC] focus:border-[#D97706] focus:outline-none"
              />
            </div>

            <label className="flex items-start gap-2.5 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3 cursor-pointer">
              <input
                type="checkbox"
                disabled={!isOwner}
                checked={projGps}
                onChange={(e) => setProjGps(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#CBD5E1] accent-[#D97706]"
              />
              <span className="text-xs text-[#475569]">
                Allow EXIF GPS retention on mobile photos
              </span>
            </label>

            {isOwner && (
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={savingSettings}
                  className="rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
                >
                  {savingSettings ? "Saving..." : "Save Changes"}
                </button>
              </div>
            )}
          </form>
        </section>

        {isOwner && (
          <section className="rounded-lg border border-[#FECACA] bg-[#FEF2F2] p-4 sm:p-6 space-y-3">
            <h3 className="text-sm font-semibold text-[#991B1B]">
              Delete Project
            </h3>
            <p className="text-xs text-[#7F1D1D]">
              Soft-deletes this project and removes it from supervisor devices on next sync. Type{" "}
              <code className="rounded bg-[#FFFFFF] px-1 py-0.5 font-mono font-semibold text-[#991B1B]">
                {project.name}
              </code>{" "}
              to confirm.
            </p>
            {deleteProjectError && (
              <p className="text-xs font-medium text-[#DC2626]">
                {deleteProjectError}
              </p>
            )}
            <input
              type="text"
              value={confirmDeleteText}
              onChange={(e) => setConfirmDeleteText(e.target.value)}
              placeholder={project.name}
              className="w-full rounded-md border border-[#FCA5A5] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#DC2626] focus:outline-none"
            />
            <button
              type="button"
              disabled={
                deletingProject || confirmDeleteText.trim() !== project.name
              }
              onClick={handleDeleteProject}
              className="w-full rounded-md bg-[#DC2626] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B91C1C] disabled:opacity-40 cursor-pointer"
            >
              {deletingProject ? "Deleting Project..." : "Delete Project"}
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
