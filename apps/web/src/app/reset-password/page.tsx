"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [token, setToken] = useState(searchParams.get("token") ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/password-reset/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim(), new_password: newPassword }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(body?.detail || `Reset failed (${res.status})`);
      }
      setDone(true);
      setTimeout(() => router.push("/login"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset password");
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

      {done ? (
        <div className="rounded-xl bg-[#F0FDF4] border border-[#BBF7D0] px-4 py-3 text-sm text-[#166534]">
          Password updated! Redirecting you to sign in…
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="token" className="block text-sm font-medium text-[#0F172A]">
              Reset Token
            </label>
            <input
              id="token"
              type="text"
              required
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste your reset token"
              className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm font-mono text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="newPassword" className="block text-sm font-medium text-[#0F172A]">
              New Password
            </label>
            <input
              id="newPassword"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-[#0F172A]">
              Confirm New Password
            </label>
            <input
              id="confirmPassword"
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
            {submitting ? "Updating password..." : "Confirm New Password"}
          </button>
        </form>
      )}

      <p className="mt-6 text-center text-xs text-[#64748B]">
        <Link href="/login" className="font-medium text-[#0F172A] hover:text-[#E05D38]">
          Back to Sign in
        </Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md mb-8">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-[#0F172A]">
          Set a new password
        </h1>
      </div>
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <Suspense fallback={<div className="bg-white p-8 rounded-2xl border border-[#E2E8F0]">Loading…</div>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
