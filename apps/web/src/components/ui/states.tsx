"use client";

import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface InlineErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
}

export function InlineErrorBanner({
  title = "Unable to load data",
  message,
  onRetry,
  retrying = false,
}: InlineErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-lg border border-[#FECACA] bg-[#FEF2F2] p-4 text-[#0F172A]"
    >
      <div className="flex items-start gap-3">
        <AlertCircle className="h-5 w-5 shrink-0 text-[#DC2626] mt-0.5" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-semibold text-[#991B1B]">{title}</p>
          <p className="text-sm text-[#7F1D1D]">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="inline-flex items-center justify-center gap-2 rounded-md border border-[#FCA5A5] bg-[#FFFFFF] px-3 py-2 text-sm font-medium text-[#991B1B] hover:bg-[#FEE2E2] disabled:opacity-50 shrink-0 cursor-pointer"
        >
          <RefreshCw
            className={`h-4 w-4 ${retrying ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          <span>{retrying ? "Retrying..." : "Retry"}</span>
        </button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  compact?: boolean;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  compact = false,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] ${
        compact ? "p-6 gap-3" : "p-8 gap-4"
      }`}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-md border border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]">
        {icon}
      </div>
      <div className="space-y-1 max-w-md">
        <p className="text-sm font-semibold text-[#0F172A]">{title}</p>
        <p className="text-sm text-[#475569]">{description}</p>
      </div>
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}

export function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded bg-[#E2E8F0]/70 ${className}`}
    />
  );
}
