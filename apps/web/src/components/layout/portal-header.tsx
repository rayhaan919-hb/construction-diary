"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronRight, HardHat, KeyRound, LogOut } from "lucide-react";
import { isDemoMode } from "@/lib/config";

interface PortalHeaderProps {
  user?: {
    full_name: string;
    email: string;
    role: "OWNER" | "SUPERVISOR";
  } | null;
  projectBreadcrumb?: {
    id: string;
    name: string;
  };
}

export function PortalHeader({ user, projectBreadcrumb }: PortalHeaderProps) {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function handleLogout() {
    setSigningOut(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <header className="sticky top-0 z-30 border-b border-[#E2E8F0] bg-[#FFFFFF]">
      <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/"
            className="flex items-center gap-2.5 text-[#0F172A] hover:opacity-90 shrink-0"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded border border-[#E2E8F0] bg-[#0F172A] text-[#D97706]">
              <HardHat className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-bold tracking-tight text-[#0F172A]">
                SITE DIARY
              </span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#64748B]">
                Owner Portal
              </span>
            </span>
          </Link>

          {projectBreadcrumb && (
            <nav aria-label="Breadcrumb" className="hidden sm:flex items-center gap-2 min-w-0">
              <ChevronRight className="h-4 w-4 text-[#94A3B8] shrink-0" />
              <Link
                href="/"
                className="text-sm text-[#475569] hover:text-[#0F172A] shrink-0"
              >
                Portfolio
              </Link>
              <ChevronRight className="h-4 w-4 text-[#94A3B8] shrink-0" />
              <span className="truncate text-sm font-semibold text-[#0F172A]">
                {projectBreadcrumb.name}
              </span>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {isDemoMode() && (
            <span className="rounded border border-[#F59E0B] bg-[#FFFBEB] px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide text-[#92400E]">
              Demo Preview
            </span>
          )}

          {user && (
            <div className="hidden md:flex items-center gap-2 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1">
              <span className="text-xs font-medium text-[#0F172A]">
                {user.full_name}
              </span>
              <span className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#475569]">
                {user.role}
              </span>
            </div>
          )}

          <Link
            href="/change-password"
            className="inline-flex items-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1.5 text-xs font-medium text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]"
            title="Change password"
          >
            <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">Password</span>
          </Link>

          <button
            type="button"
            onClick={handleLogout}
            disabled={signingOut}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1.5 text-xs font-medium text-[#475569] hover:bg-[#FEF2F2] hover:border-[#FECACA] hover:text-[#DC2626] disabled:opacity-50 cursor-pointer"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{signingOut ? "Signing out..." : "Sign out"}</span>
          </button>
        </div>
      </div>
    </header>
  );
}
