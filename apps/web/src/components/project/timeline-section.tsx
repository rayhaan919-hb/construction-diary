"use client";

import React, { useMemo, useState } from "react";
import { Calendar, Clock, FileDown, History, RefreshCw, Search } from "lucide-react";
import type { DailyReport, SiteLog, User } from "@/lib/types";
import { formatDateShort } from "@/lib/format";
import { downloadDailyReportPdf } from "@/lib/pdf/download-pdf";
import {
  EmptyState,
  InlineErrorBanner,
  SkeletonBlock,
} from "@/components/ui/states";
import type { LightboxImage } from "@/components/ui/photo-lightbox";
import { LogNoteCard } from "./log-note-card";

type TimelineFilter = "ALL" | "BLOCKERS" | "VOICE" | "FAILED";

interface TimelineSectionProps {
  projectId: string;
  timezone: string;
  currentUser: User | null;
  days: DailyReport[] | null;
  nextBefore: string | null;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  loadMoreError: string | null;
  onRetry: () => void;
  onLoadMore: () => void;
  onRetryExtraction: (logId: string) => Promise<void>;
  onEditLog: (logId: string, notes: string) => Promise<void>;
  onDeleteLog: (logId: string) => Promise<void>;
  onViewPhoto: (image: LightboxImage) => void;
}

export function TimelineSection({
  projectId,
  timezone,
  currentUser,
  days,
  nextBefore,
  loading,
  loadingMore,
  error,
  loadMoreError,
  onRetry,
  onLoadMore,
  onRetryExtraction,
  onEditLog,
  onDeleteLog,
  onViewPhoto,
}: TimelineSectionProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<TimelineFilter>("ALL");
  const [exportingDate, setExportingDate] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const filteredDays = useMemo(() => {
    if (!days) return null;
    const q = searchQuery.trim().toLowerCase();
    const matchesLog = (log: SiteLog): boolean => {
      if (filter === "BLOCKERS" && !(log.structured_summary?.blockers?.length)) {
        return false;
      }
      if (filter === "VOICE" && !log.audio_uri && !log.audio_duration_ms) {
        return false;
      }
      if (filter === "FAILED" && log.extraction_status !== "FAILED") {
        return false;
      }
      if (!q) return true;
      const hay = [
        log.author_name ?? "",
        log.notes ?? "",
        log.transcript ?? "",
        log.log_date,
        ...(log.structured_summary?.tasks_completed ?? []),
        ...(log.structured_summary?.material_deliveries ?? []),
        ...(log.structured_summary?.blockers ?? []),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    };

    return days
      .map((day) => ({
        ...day,
        logs: day.logs.filter(matchesLog),
      }))
      .filter((day) => day.logs.length > 0 || (!q && filter === "ALL"));
  }, [days, searchQuery, filter]);

  async function handleExportPdf(dateStr: string) {
    setExportError(null);
    setExportingDate(dateStr);
    try {
      await downloadDailyReportPdf(projectId, dateStr);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Failed to export PDF");
    } finally {
      setExportingDate(null);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
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

      {/* Search & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#94A3B8]" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search notes, transcripts, blockers, or author..."
            className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] py-1.5 pl-8 pr-3 text-xs text-[#0F172A] focus:border-[#D97706] focus:outline-none"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {(
            [
              ["ALL", "All"],
              ["BLOCKERS", "Blockers"],
              ["VOICE", "Voice"],
              ["FAILED", "Failed AI"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={`rounded-md border px-2.5 py-1 text-xs font-medium cursor-pointer ${
                filter === key
                  ? "border-[#D97706] bg-[#FFFBEB] text-[#92400E]"
                  : "border-[#E2E8F0] bg-[#FFFFFF] text-[#475569] hover:text-[#0F172A]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {exportError && (
        <InlineErrorBanner
          title="PDF Export Error"
          message={exportError}
        />
      )}

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
      ) : !filteredDays || filteredDays.length === 0 ? (
        <EmptyState
          icon={<Calendar className="h-5 w-5" />}
          title={days && days.length > 0 ? "No matching logs" : "No daily logs recorded yet"}
          description={
            days && days.length > 0
              ? "Try clearing your search query or switching the log filter."
              : "When supervisors record voice notes or photos in the mobile field app, day-grouped reports appear here."
          }
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
          {filteredDays.map((day) => {
            const isExporting = exportingDate === day.log_date;
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

                  <button
                    type="button"
                    disabled={isExporting}
                    onClick={() => handleExportPdf(day.log_date)}
                    className="inline-flex items-center justify-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-1.5 text-xs font-semibold text-[#0F172A] hover:border-[#D97706] hover:text-[#B45309] disabled:opacity-50 shrink-0 cursor-pointer"
                  >
                    <FileDown className="h-3.5 w-3.5 text-[#D97706]" aria-hidden="true" />
                    <span>{isExporting ? "Rendering PDF..." : "Export PDF"}</span>
                  </button>
                </div>

                {/* Day Logs */}
                <div className="p-4 space-y-3">
                  {day.logs.map((log) => (
                    <LogNoteCard
                      key={log.id}
                      log={log}
                      timezone={timezone}
                      canManage={
                        currentUser?.role === "OWNER" ||
                        log.author_id === currentUser?.id
                      }
                      onRetryExtraction={onRetryExtraction}
                      onEditLog={onEditLog}
                      onDeleteLog={onDeleteLog}
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
