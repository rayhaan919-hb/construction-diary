"use client";

import React from "react";
import Link from "next/link";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-6">
      <div className="w-full max-w-md rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-6 space-y-4">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-6 w-6 shrink-0 text-[#DC2626]" />
          <div className="space-y-1">
            <h1 className="text-base font-bold text-[#0F172A]">
              Something went wrong
            </h1>
            <p className="text-sm text-[#475569]">
              {error.message || "An unexpected portal error occurred."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
          >
            <RefreshCw className="h-4 w-4" />
            <span>Try Again</span>
          </button>
          <Link
            href="/"
            className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2 text-sm font-medium text-[#475569] hover:bg-[#F8FAFC]"
          >
            Portfolio Home
          </Link>
        </div>
      </div>
    </main>
  );
}
