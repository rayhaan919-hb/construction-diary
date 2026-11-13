"use client";

import React from "react";
import {
  AlertTriangle,
  Calendar,
  Camera,
  CheckCircle2,
  ClipboardList,
  Clock,
  FileDown,
  Package,
  Users,
} from "lucide-react";
import type { DailyReport } from "@/lib/types";
import { formatDateShort, formatTimeInZone } from "@/lib/format";
import {
  EmptyState,
  InlineErrorBanner,
  SkeletonBlock,
} from "@/components/ui/states";
import type { LightboxImage } from "@/components/ui/photo-lightbox";

interface TodayBentoTilesProps {
  projectId: string;
  timezone: string;
  todayDate: string;
  report: DailyReport | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onViewPhoto: (image: LightboxImage) => void;
}

export function TodayBentoTiles({
  projectId,
  timezone,
  todayDate,
  report,
  loading,
  error,
  onRetry,
  onViewPhoto,
}: TodayBentoTilesProps) {
  const photosWithMeta =
    report?.logs.flatMap((log) =>
      (log.photos ?? []).map((photo) => ({
        photo,
        author: log.author_name ?? "Supervisor",
        recordedAt: log.recorded_at,
      }))
    ) ?? [];

  const pdfHref = `/api/reports/${projectId}/${todayDate}/pdf`;

  return (
    <>
      {/* Tile 2: Project-local Today Summary */}
      <section className="flex flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
        <div className="flex items-center justify-between gap-3 border-b border-[#E2E8F0] px-4 py-3">
          <div className="flex items-center gap-2 min-w-0">
            <Calendar className="h-4 w-4 text-[#D97706] shrink-0" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-[#0F172A]">Today Summary</h2>
            <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
              {todayDate}
            </span>
          </div>
          <a
            href={pdfHref}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-2.5 py-1.5 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B45309] shrink-0"
          >
            <FileDown className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Export Today PDF</span>
          </a>
        </div>

        <div className="flex-1 p-4 space-y-4">
          {loading ? (
            <div className="space-y-3" aria-busy="true">
              <div className="grid grid-cols-2 gap-3">
                <SkeletonBlock className="h-20 w-full" />
                <SkeletonBlock className="h-20 w-full" />
              </div>
              <SkeletonBlock className="h-4 w-40" />
              <SkeletonBlock className="h-4 w-56" />
              <SkeletonBlock className="h-4 w-48" />
            </div>
          ) : error ? (
            <InlineErrorBanner
              title="Failed to load today's rollup"
              message={error}
              onRetry={onRetry}
            />
          ) : !report || report.log_count === 0 ? (
            <EmptyState
              compact
              icon={<ClipboardList className="h-5 w-5" />}
              title={`No logs yet for ${formatDateShort(todayDate)}`}
              description="Supervisor voice and photo logs captured on site today will automatically summarize here."
            />
          ) : (
            <>
              {report.pending_extraction_count > 0 && (
                <div className="flex items-start gap-2 rounded-md border border-[#FDE68A] bg-[#FFFBEB] p-3 text-xs text-[#92400E]">
                  <Clock className="h-4 w-4 shrink-0 text-[#D97706] mt-0.5" />
                  <span>
                    <strong className="font-mono tabular-nums">
                      {report.pending_extraction_count}
                    </strong>{" "}
                    log(s) pending or processing AI extraction — summary totals may update shortly.
                  </span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-[#64748B]">
                    <Users className="h-3.5 w-3.5 text-[#D97706]" />
                    <span>Peak Crew (labor_max)</span>
                  </div>
                  <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-[#0F172A]">
                    {report.labor_max !== null && report.labor_max !== undefined
                      ? report.labor_max
                      : "—"}
                  </p>
                </div>

                <div className="rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-[#64748B]">
                    <ClipboardList className="h-3.5 w-3.5 text-[#475569]" />
                    <span>Site Logs Today</span>
                  </div>
                  <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-[#0F172A]">
                    {report.log_count}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                  Tasks Completed
                </h3>
                {report.tasks_completed.length === 0 ? (
                  <p className="text-xs text-[#64748B]">
                    No tasks extracted from today&apos;s notes yet.
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {report.tasks_completed.map((task, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-sm text-[#0F172A]"
                      >
                        <CheckCircle2
                          className="h-4 w-4 shrink-0 text-[#059669] mt-0.5"
                          aria-hidden="true"
                        />
                        <span>{task}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      </section>

      {/* Tile 3, 4, 5: Blockers, Material Deliveries, Photo Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:col-span-2">
        {/* Tile 3: Blockers */}
        <section className="flex flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] px-4 py-3">
            <div className="flex items-center gap-2">
              <AlertTriangle
                className="h-4 w-4 text-[#EA580C]"
                aria-hidden="true"
              />
              <h2 className="text-sm font-semibold text-[#0F172A]">
                Today&apos;s Blockers
              </h2>
            </div>
            {report && (
              <span
                className={`rounded border px-1.5 py-0.5 font-mono text-xs font-semibold tabular-nums ${
                  report.blockers.length > 0
                    ? "border-[#FED7AA] bg-[#FFF7ED] text-[#EA580C]"
                    : "border-[#E2E8F0] bg-[#F8FAFC] text-[#475569]"
                }`}
              >
                {report.blockers.length}
              </span>
            )}
          </div>
          <div className="flex-1 p-4">
            {loading ? (
              <div className="space-y-2">
                <SkeletonBlock className="h-4 w-full" />
                <SkeletonBlock className="h-4 w-4/5" />
              </div>
            ) : error ? (
              <InlineErrorBanner message={error} onRetry={onRetry} />
            ) : !report || report.blockers.length === 0 ? (
              <EmptyState
                compact
                icon={<CheckCircle2 className="h-4 w-4 text-[#059669]" />}
                title="No active blockers"
                description="No site delays or safety blockers flagged today."
              />
            ) : (
              <ul className="space-y-2">
                {report.blockers.map((blocker, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 rounded border border-[#FED7AA] bg-[#FFF7ED] px-3 py-2 text-xs text-[#9A3412]"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-[#EA580C] mt-0.5" />
                    <span>{blocker}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* Tile 4: Material Deliveries */}
        <section className="flex flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] px-4 py-3">
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-[#0F172A]">
                Material Deliveries
              </h2>
            </div>
            {report && (
              <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
                {report.material_deliveries.length}
              </span>
            )}
          </div>
          <div className="flex-1 p-4">
            {loading ? (
              <div className="space-y-2">
                <SkeletonBlock className="h-4 w-full" />
                <SkeletonBlock className="h-4 w-3/4" />
              </div>
            ) : error ? (
              <InlineErrorBanner message={error} onRetry={onRetry} />
            ) : !report || report.material_deliveries.length === 0 ? (
              <EmptyState
                compact
                icon={<Package className="h-4 w-4" />}
                title="No deliveries today"
                description="Material arrivals mentioned in voice logs appear here."
              />
            ) : (
              <ul className="space-y-2">
                {report.material_deliveries.map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-xs text-[#0F172A]"
                  >
                    <Package className="h-3.5 w-3.5 shrink-0 text-[#64748B] mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        {/* Tile 5: Today's Site Photo Strip */}
        <section className="flex flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] px-4 py-3">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-[#0F172A]">
                Today&apos;s Photo Strip
              </h2>
            </div>
            {report && (
              <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
                {photosWithMeta.length}
              </span>
            )}
          </div>
          <div className="flex-1 p-4">
            {loading ? (
              <div className="grid grid-cols-3 gap-2">
                <SkeletonBlock className="aspect-square w-full" />
                <SkeletonBlock className="aspect-square w-full" />
                <SkeletonBlock className="aspect-square w-full" />
              </div>
            ) : error ? (
              <InlineErrorBanner message={error} onRetry={onRetry} />
            ) : photosWithMeta.length === 0 ? (
              <EmptyState
                compact
                icon={<Camera className="h-4 w-4" />}
                title="No site photos today"
                description="Photos attached to today's site logs show here."
              />
            ) : (
              <div className="grid grid-cols-3 gap-2">
                {photosWithMeta.map(({ photo, author, recordedAt }) =>
                  photo.url ? (
                    <button
                      key={photo.id}
                      type="button"
                      onClick={() =>
                        onViewPhoto({
                          url: photo.url as string,
                          title: `Site Photo · ${formatTimeInZone(
                            recordedAt,
                            timezone
                          )}`,
                          meta: `Uploaded by ${author}`,
                        })
                      }
                      className="group relative aspect-square overflow-hidden rounded border border-[#E2E8F0] bg-[#F8FAFC] hover:border-[#D97706] cursor-pointer"
                    >
                      <img
                        src={photo.url}
                        alt={`Site photo by ${author}`}
                        className="h-full w-full object-cover"
                      />
                    </button>
                  ) : (
                    <div
                      key={photo.id}
                      className="flex aspect-square items-center justify-center rounded border border-[#E2E8F0] bg-[#F8FAFC] p-1 text-center font-mono text-[10px] text-[#64748B]"
                    >
                      {photo.upload_status}
                    </div>
                  )
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
