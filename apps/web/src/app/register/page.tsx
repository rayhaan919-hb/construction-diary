"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import type { PlanTier } from "@/lib/types";

export default function RegisterPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [companySlug, setCompanySlug] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [planTier, setPlanTier] = useState<PlanTier>("FREE");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: companyName.trim(),
          company_slug: companySlug.trim() || undefined,
          owner_full_name: fullName.trim(),
          owner_email: email.trim(),
          password,
          preferred_locale: "en",
          plan_tier: planTier,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: string; title?: string } | null;
        throw new Error(body?.detail || body?.title || `Registration failed (${res.status})`);
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create organization");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="flex items-center justify-center gap-3 mb-6">
          <div className="h-10 w-10 rounded-xl bg-[#0F172A] flex items-center justify-center shadow-sm">
            <span className="h-3.5 w-3.5 rounded-full bg-[#E05D38]" />
          </div>
          <div>
            <p className="text-xl font-bold tracking-tight text-[#0F172A]">SiteDiary</p>
            <p className="text-xs text-[#64748B]">Construction SaaS Workspace</p>
          </div>
        </div>
        <h1 className="text-center text-2xl font-semibold tracking-tight text-[#0F172A]">
          Create your company workspace
        </h1>
        <p className="mt-2 text-center text-sm text-[#64748B]">
          Register an Owner account to manage projects, supervisors, permits, and PDF reports.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="bg-white py-8 px-6 shadow-sm border border-[#E2E8F0] rounded-2xl sm:px-10">
          {error ? (
            <div
              role="alert"
              className="mb-6 rounded-xl bg-[#FEF2F2] border border-[#FECACA] px-4 py-3 text-sm text-[#B91C1C]"
            >
              {error}
            </div>
          ) : null}

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label htmlFor="companyName" className="block text-sm font-medium text-[#0F172A]">
                Company Name
              </label>
              <input
                id="companyName"
                type="text"
                required
                minLength={2}
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="e.g. Siddiqui Builders & Developers"
                className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="companySlug" className="block text-sm font-medium text-[#0F172A]">
                Workspace Slug <span className="text-xs font-normal text-[#64748B]">(optional)</span>
              </label>
              <input
                id="companySlug"
                type="text"
                pattern="[a-z0-9-]*"
                value={companySlug}
                onChange={(e) => setCompanySlug(e.target.value.toLowerCase())}
                placeholder="siddiqui-builders"
                className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-[#0F172A]">
                  Owner Full Name
                </label>
                <input
                  id="fullName"
                  type="text"
                  required
                  minLength={2}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Kamran Siddiqui"
                  className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="planTier" className="block text-sm font-medium text-[#0F172A]">
                  Starting Plan
                </label>
                <select
                  id="planTier"
                  value={planTier}
                  onChange={(e) => setPlanTier(e.target.value as PlanTier)}
                  className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] bg-white px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
                >
                  <option value="FREE">Free (3 projects, 5 seats)</option>
                  <option value="PRO">Pro Trial (25 projects, 50 seats)</option>
                  <option value="ENTERPRISE">Enterprise Trial</option>
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-[#0F172A]">
                Work Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="owner@company.com"
                className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-[#0F172A]">
                Password <span className="text-xs font-normal text-[#64748B]">(min 8 characters)</span>
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1.5 block w-full rounded-xl border border-[#CBD5E1] px-3.5 py-2.5 text-sm text-[#0F172A] focus:border-[#0F172A] focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-[#0F172A] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1E293B] disabled:opacity-50 transition-colors"
            >
              {submitting ? "Creating workspace..." : "Create Organization & Sign In"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[#64748B]">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[#0F172A] hover:text-[#E05D38]">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
