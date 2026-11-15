"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

function AcceptInviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") ?? "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/accept-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim(), password }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail || `Could not accept invitation (${res.status})`);
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept invitation");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="bg-white py-8 px-6 shadow-sm border border-[#E2E8F0] rounded-2xl sm:px-10">
      {error ? (
        <div
          role="alert"
          className="mb-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] px-4 py-3 text-sm text-[#B91C1C]"
        >
          {error}
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="inviteToken" className="block text-sm font-medium text-[#0F172A]">
            Invitation Token
          </label>
          <input
            id="inviteToken"
            type="text"
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Paste the invite token provided by your Owner"
            className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm font-mono text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="invitePassword" className="block text-sm font-medium text-[#0F172A]">
            Choose Your Password
          </label>
          <input
            id="invitePassword"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="confirmInvitePassword" className="block text-sm font-medium text-[#0F172A]">
            Confirm Password
          </label>
          <input
            id="confirmInvitePassword"
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-xl bg-[#0F172A] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1E293B] disabled:opacity-50"
        >
          {submitting ? "Activating account..." : "Accept Invitation & Sign In"}
        </button>
      </form>

      <p className="mt-6 text-center text-xs text-[#64748B]">
        <Link href="/login" className="font-medium text-[#0F172A] hover:text-[#E05D38]">
          Back to Sign in
        </Link>
      </p>
    </div>
  );
}

export default function InvitePage() {
  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md mb-8">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-[#0F172A]">
          Accept Team Invitation
        </h1>
        <p className="mt-2 text-center text-sm text-[#64748B]">
          Activate your SiteDiary account and join your company workspace.
        </p>
      </div>
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Suspense fallback={<div className="bg-white p-8 rounded-2xl border border-[#E2E8F0]">Loading…</div>}>
          <AcceptInviteForm />
        </Suspense>
      </div>
    </div>
  );
}
