import React from "react";
import Link from "next/link";
import { HardHat } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8FAFC] p-6">
      <div className="w-full max-w-md rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-6 text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-md border border-[#E2E8F0] bg-[#0F172A] text-[#D97706]">
          <HardHat className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <p className="font-mono text-xs font-bold uppercase tracking-wider text-[#D97706]">
            404 · Not Found
          </p>
          <h1 className="text-lg font-bold text-[#0F172A]">
            Page not found
          </h1>
          <p className="text-sm text-[#475569]">
            The requested project or page does not exist or you no longer have access.
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309]"
        >
          Return to Portfolio
        </Link>
      </div>
    </main>
  );
}
