"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, CheckCircle2, KeyRound, ShieldAlert } from "lucide-react";
import type { User } from "@/lib/types";
import { PortalHeader } from "@/components/layout/portal-header";
import { InlineErrorBanner } from "@/components/ui/states";

export function ChangePasswordView({
  user,
  initialError,
}: {
  user: User | null;
  initialError: string | null;
}) {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
        credentials: "same-origin",
      });

      if (!res.ok) {
        let msg = `Password update failed (${res.status})`;
        try {
          const problem = (await res.json()) as {
            detail?: string;
            title?: string;
          };
          msg = problem.detail || problem.title || msg;
        } catch {
          // ignore
        }
        setError(msg);
        return;
      }

      setSuccess(true);
      setTimeout(() => {
        router.replace("/");
        router.refresh();
      }, 600);
    } catch {
      setError("Network error while updating password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <PortalHeader user={user} />

      <main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6">
        <div className="mx-auto max-w-md space-y-4">
          {!user?.must_change_password && (
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[#475569] hover:text-[#0F172A]"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Portfolio</span>
            </Link>
          )}

          {initialError && (
            <InlineErrorBanner
              title="Could not verify account status"
              message={initialError}
              onRetry={() => router.refresh()}
            />
          )}

          {user?.must_change_password && (
            <div className="flex items-start gap-3 rounded-lg border border-[#FED7AA] bg-[#FFF7ED] p-4 text-sm text-[#9A3412]">
              <ShieldAlert className="h-5 w-5 shrink-0 text-[#EA580C] mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold">Password change required</p>
                <p>
                  You signed in with a temporary password. Set a new permanent password before accessing site projects.
                </p>
              </div>
            </div>
          )}

          <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-6 space-y-6">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded border border-[#E2E8F0] bg-[#F8FAFC] text-[#D97706]">
                <KeyRound className="h-4 w-4" />
              </span>
              <div>
                <h1 className="text-base font-semibold text-[#0F172A]">
                  Update Password
                </h1>
                <p className="text-xs text-[#475569] font-mono">
                  {user?.email ?? "Account security"}
                </p>
              </div>
            </div>

            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-md border border-[#FECACA] bg-[#FEF2F2] p-3 text-sm text-[#991B1B]"
              >
                <AlertCircle className="h-4 w-4 shrink-0 text-[#DC2626] mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div
                role="status"
                className="flex items-center gap-2.5 rounded-md border border-[#A7F3D0] bg-[#ECFDF5] p-3 text-sm font-medium text-[#065F46]"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-[#059669]" />
                <span>Password updated. Redirecting to portfolio...</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="current_password"
                  className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
                >
                  Current Password
                </label>
                <input
                  id="current_password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="new_password"
                  className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
                >
                  New Password (min 8 chars)
                </label>
                <input
                  id="new_password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="confirm_password"
                  className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
                >
                  Confirm New Password
                </label>
                <input
                  id="confirm_password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={submitting || success}
                className="w-full rounded-md bg-[#D97706] px-4 py-2.5 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
              >
                {submitting ? "Updating..." : "Save New Password"}
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
