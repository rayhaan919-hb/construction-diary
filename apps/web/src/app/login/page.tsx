"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, HardHat, Lock, Mail } from "lucide-react";

function sanitizeNextPath(raw: string | null): string {
  if (
    !raw ||
    !raw.startsWith("/") ||
    raw.startsWith("//") ||
    raw.startsWith("/\\") ||
    raw.includes("\\")
  ) {
    return "/";
  }
  return raw;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = sanitizeNextPath(searchParams.get("next"));

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
        credentials: "same-origin",
      });

      if (!res.ok) {
        let msg = `Sign in failed (${res.status})`;
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

      const data = (await res.json()) as {
        user?: { must_change_password?: boolean };
      };

      if (data.user?.must_change_password) {
        router.replace("/change-password");
      } else {
        router.replace(nextPath);
      }
      router.refresh();
    } catch {
      setError("Network error while signing in. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-4">
      <div className="w-full max-w-[420px] overflow-hidden rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="h-1 w-full bg-[#D97706]" />
        <div className="p-6 sm:p-8 space-y-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-md border border-[#E2E8F0] bg-[#0F172A] text-[#D97706]">
              <HardHat className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-[#0F172A]">
                Site Diary Owner Portal
              </h1>
              <p className="text-sm text-[#475569]">
                Permits, voice logs, and daily PDF reports
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

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Work Email
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#94A3B8]" />
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="owner@example.com"
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] py-2 pl-9 pr-3 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#D97706] focus:outline-none"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-[#94A3B8]" />
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  minLength={8}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] py-2 pl-9 pr-3 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#D97706] focus:outline-none"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-md bg-[#D97706] px-4 py-2.5 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
            >
              {submitting ? "Signing in..." : "Sign in to Portal"}
            </button>
          </form>

          <div className="flex items-center justify-between text-xs">
            <Link
              href="/forgot-password"
              className="font-medium text-[#475569] hover:text-[#D97706]"
            >
              Forgot password?
            </Link>
            <Link
              href="/register"
              className="font-semibold text-[#D97706] hover:text-[#B45309]"
            >
              Create company account
            </Link>
          </div>

          <p className="border-t border-[#E2E8F0] pt-4 text-xs text-[#64748B]">
            Session tokens are stored in httpOnly cookies. Supervisors use the Android field app for offline capture.
          </p>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-4">
          <div className="h-[380px] w-full max-w-[420px] animate-pulse rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]" />
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
