"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [devResetToken, setDevResetToken] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResultMessage(null);
    setDevResetToken(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/password-reset/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = (await res.json().catch(() => null)) as {
        message?: string;
        detail?: string;
        dev_reset_token?: string | null;
      } | null;
      if (!res.ok) {
        throw new Error(data?.detail || `Request failed (${res.status})`);
      }
      setResultMessage(
        data?.message ?? "If an account exists for that email, a reset link has been issued."
      );
      if (data?.dev_reset_token) {
        setDevResetToken(data.dev_reset_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request password reset");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <h1 className="text-center text-2xl font-semibold tracking-tight text-[#0F172A]">
          Reset your password
        </h1>
        <p className="mt-2 text-center text-sm text-[#64748B]">
          Enter your SiteDiary account email to receive a reset token.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm border border-[#E2E8F0] rounded-2xl sm:px-10">
          {error ? (
            <div
              role="alert"
              className="mb-4 rounded-xl bg-[#FEF2F2] border border-[#FECACA] px-4 py-3 text-sm text-[#B91C1C]"
            >
              {error}
            </div>
          ) : null}

          {resultMessage ? (
            <div className="mb-4 rounded-xl bg-[#F0FDF4] border border-[#BBF7D0] px-4 py-3 text-sm text-[#166534] space-y-2">
              <p>{resultMessage}</p>
              {devResetToken ? (
                <div className="pt-1">
                  <p className="text-xs font-medium">Development reset token:</p>
                  <code className="block break-all rounded bg-white/80 px-2 py-1 text-xs font-mono text-[#0F172A] mt-1">
                    {devResetToken}
                  </code>
                  <Link
                    href={`/reset-password?token=${encodeURIComponent(devResetToken)}`}
                    className="inline-block mt-2 text-xs font-semibold underline"
                  >
                    Continue to set new password →
                  </Link>
                </div>
              ) : null}
            </div>
          ) : null}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-[#0F172A]">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-[#0F172A] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1E293B] disabled:opacity-50"
            >
              {submitting ? "Sending request..." : "Request Password Reset"}
            </button>
          </form>

          <div className="mt-6 flex items-center justify-between text-xs text-[#64748B]">
            <Link href="/reset-password" className="hover:text-[#0F172A]">
              Already have a token?
            </Link>
            <Link href="/login" className="font-medium text-[#0F172A] hover:text-[#E05D38]">
              Back to Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
