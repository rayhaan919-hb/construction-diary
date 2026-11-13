"use client";

import React from "react";
import { Calendar, Clock, FileDown, History, RefreshCw } from "lucide-react";
import type { DailyReport } from "@/lib/types";
import { formatDateShort } from "@/lib/format";
import {
  EmptyState,
  InlineErrorBanner,
  SkeletonBlock,
} from "@/components/ui/states";
import type { LightboxImage } from "@/components/ui/photo-lightbox";
import { LogNoteCard } from "./log-note-card";

interface TimelineSectionProps {
  projectId: string;
  timezone: string;
  days: DailyReport[] | null;
  nextBefore: string | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;
  onRetry: () => void;
  onLoadMore: () => void;
  onRetryExtraction: (logId: string) => Promise<void>;
  onViewPhoto: (image: LightboxImage) => void;
}

export function TimelineSection({
  projectId,
  timezone,
  days,
  nextBefore,
  loading,
  loadingMore,
  error,
  loadMoreError,
  onRetry,
  onLoadMore,
  onRetryExtraction,
  onViewPhoto,
}: TimelineSectionProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[#0F172A]">
            Daily Site Timeline
          </h2>
        </div>
        <button
          type="button"
          onClick={onRetry}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1.5 text-xs font-medium text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A] disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          <span>Refresh Timeline</span>
        </button>
      </div>

      {loading ? (
        <div className="space-y-4" aria-busy="true">
          {[0, 1].map((dayIdx) => (
            <div
              key={dayIdx}
              className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3"
            >
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
                <SkeletonBlock className="h-5 w-48" />
                <SkeletonBlock className="h-8 w-28" />
              </div>
              <SkeletonBlock className="h-28 w-full" />
              <SkeletonBlock className="h-24 w-full" />
            </div>
          ))}
        </div>
      ) : error ? (
        <InlineErrorBanner
          title="Could not load project timeline"
          message={error}
          onRetry={onRetry}
        />
      ) : !days || days.length === 0 ? (
        <EmptyState
          icon={<Calendar className="h-5 w-5" />}
          title="No daily logs recorded yet"
          description="When supervisors record voice notes or photos in the mobile field app, day-grouped reports appear here."
          action={
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              <span>Check for Logs</span>
            </button>
          }
        />
      ) : (
        <div className="space-y-6">
          {days.map((day) => {
            const pdfUrl = `/api/reports/${projectId}/${day.log_date}/pdf`;
            return (
              <div
                key={day.log_date}
                className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]"
              >
                {/* Day Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 rounded-t-lg">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h3 className="text-sm font-bold text-[#0F172A]">
                      {formatDateShort(day.log_date)}
                    </h3>
                    <span className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
                      {day.log_date}
                    </span>
                    <span className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-0.5 font-mono text-xs tabular-nums text-[#0F172A]">
                      Labor Peak:{" "}
                      {day.labor_max !== null && day.labor_max !== undefined
                        ? day.labor_max
                        : "—"}
                    </span>
                    <span className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
                      {day.log_count} {day.log_count === 1 ? "log" : "logs"}
                    </span>
                    {day.pending_extraction_count > 0 && (
                      <span className="inline-flex items-center gap-1 rounded border border-[#FDE68A] bg-[#FFFBEB] px-2 py-0.5 font-mono text-xs tabular-nums text-[#92400E]">
                        <Clock className="h-3 w-3 text-[#D97706]" />
                        {day.pending_extraction_count} pending
                      </span>
                    )}
                  </div>

                  <a
                    href={pdfUrl}
                    className="inline-flex items-center justify-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1.5 text-xs font-semibold text-[#0F172A] hover:border-[#D97706] hover:text-[#B45309] shrink-0"
                  >
                    <FileDown className="h-3.5 w-3.5 text-[#D97706]" aria-hidden="true" />
                    <span>Export PDF</span>
                  </a>
                </div>

                {/* Day Logs */}
                <div className="p-4 space-y-3">
                  {day.logs.map((log) => (
                    <LogNoteCard
                      key={log.id}
                      log={log}
                      timezone={timezone}
                      onRetryExtraction={onRetryExtraction}
                      onViewPhoto={onViewPhoto}
                    />
                  ))}
                </div>
              </div>
            );
          })}

          {loadMoreError && (
            <InlineErrorBanner
              title="Could not load older days"
              message={loadMoreError}
              onRetry={onLoadMore}
              retrying={loadingMore}
            />
          )}

          {nextBefore !== null && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={onLoadMore}
                disabled={loadingMore}
                className="inline-flex items-center gap-2 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2 text-sm font-medium text-[#0F172A] hover:border-[#D97706] hover:bg-[#F8FAFC] disabled:opacity-50 cursor-pointer"
              >
                {loadingMore ? "Loading older days..." : "Load older days"}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
