"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  FileDown,
  LayoutGrid,
  MapPin,
  Users,
} from "lucide-react";
import type {
  DailyReport,
  ExtractQueueResponse,
  Member,
  Permit,
  Project,
  SiteLog,
  TimelineResponse,
  User,
} from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getTodayInTimezone } from "@/lib/format";
import { downloadDailyReportPdf } from "@/lib/pdf/download-pdf";
import { getErrorMessage } from "@/lib/problem";
import { PortalHeader } from "@/components/layout/portal-header";
import { InlineErrorBanner } from "@/components/ui/states";
import {
  type LightboxImage,
  PhotoLightbox,
} from "@/components/ui/photo-lightbox";
import { PermitsTile } from "./permits-tile";
import { PermitModal } from "./permit-modal";
import { TodayBentoTiles } from "./today-bento-tiles";
import { TimelineSection } from "./timeline-section";
import { TeamSettingsPanel } from "./team-settings-panel";
import { ProjectDashboardSkeleton } from "./project-dashboard-skeleton";

interface ProjectDashboardViewProps {
  projectId: string;
  user: User | null;
  initialProject: Project | null;
  initialProjectError: string | null;
  initialTodayDate: string;
  initialPermits: Permit[] | null;
  initialPermitsError: string | null;
  initialTodayReport: DailyReport | null;
  initialTodayError: string | null;
  initialTimeline: TimelineResponse | null;
  initialTimelineError: string | null;
  initialMembers: Member[] | null;
  initialMembersError: string | null;
}

export function ProjectDashboardView({
  projectId,
  user,
  initialProject,
  initialProjectError,
  initialTodayDate,
  initialPermits,
  initialPermitsError,
  initialTodayReport,
  initialTodayError,
  initialTimeline,
  initialTimelineError,
  initialMembers,
  initialMembersError,
}: ProjectDashboardViewProps) {
  const [activeTab, setActiveTab] = useState<"overview" | "team">("overview");
  const [project, setProject] = useState<Project | null>(initialProject);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(
    initialProjectError
  );

  const [permits, setPermits] = useState<Permit[] | null>(initialPermits);
  const [permitsLoading, setPermitsLoading] = useState(false);
  const [permitsError, setPermitsError] = useState<string | null>(
    initialPermitsError
  );

  const [todayReport, setTodayReport] = useState<DailyReport | null>(
    initialTodayReport
  );
  const [todayLoading, setTodayLoading] = useState(false);
  const [todayError, setTodayError] = useState<string | null>(
    initialTodayError
  );

  const [timelineDays, setTimelineDays] = useState<DailyReport[] | null>(
    initialTimeline?.days ?? null
  );
  const [nextBefore, setNextBefore] = useState<string | null>(
    initialTimeline?.next_before ?? null
  );
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(
    initialTimelineError
  );
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);

  const [members, setMembers] = useState<Member[] | null>(initialMembers);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(
    initialMembersError
  );

  const [permitModalOpen, setPermitModalOpen] = useState(false);
  const [editingPermit, setEditingPermit] = useState<Permit | null>(null);
  const [lightboxImage, setLightboxImage] = useState<LightboxImage | null>(null);
  const [exportingTodayPdf, setExportingTodayPdf] = useState(false);
  const [todayPdfError, setTodayPdfError] = useState<string | null>(null);

  const isOwner = user?.role === "OWNER";
  const effectiveTimezone = project?.timezone ?? "Asia/Karachi";
  const todayDate = project
    ? getTodayInTimezone(project.timezone)
    : initialTodayDate;

  const hasPendingExtraction = Boolean(
    timelineDays?.some((day) =>
      day.logs.some(
        (log) =>
          log.extraction_status === "PROCESSING" ||
          log.extraction_status === "PENDING"
      )
    )
  );

  useEffect(() => {
    if (!hasPendingExtraction || !project) return;
    const intervalId = setInterval(() => {
      void bffFetch<TimelineResponse>(`/v1/projects/${projectId}/timeline?days=7`)
        .then((resp) => {
          setTimelineDays(resp.days);
          setNextBefore(resp.next_before);
        })
        .catch(() => {
          // Transient polling errors are ignored until next interval
        });
    }, 4000);
    return () => clearInterval(intervalId);
  }, [hasPendingExtraction, project, projectId]);

  async function reloadPermits() {
    setPermitsLoading(true);
    setPermitsError(null);
    try {
      const list = await bffFetch<Permit[]>(`/v1/projects/${projectId}/permits`);
      setPermits(list);
    } catch (err) {
      setPermitsError(getErrorMessage(err, "Failed to load permits"));
    } finally {
      setPermitsLoading(false);
    }
  }

  async function reloadToday(tz = effectiveTimezone) {
    const dateStr = getTodayInTimezone(tz);
    setTodayLoading(true);
    setTodayError(null);
    try {
      const report = await bffFetch<DailyReport>(
        `/v1/projects/${projectId}/days/${dateStr}`
      );
      setTodayReport(report);
    } catch (err) {
      setTodayError(getErrorMessage(err, "Failed to load today's report"));
    } finally {
      setTodayLoading(false);
    }
  }

  async function reloadTimeline() {
    setTimelineLoading(true);
    setTimelineError(null);
    setLoadMoreError(null);
    try {
      const resp = await bffFetch<TimelineResponse>(
        `/v1/projects/${projectId}/timeline?days=7`
      );
      setTimelineDays(resp.days);
      setNextBefore(resp.next_before);
    } catch (err) {
      setTimelineError(getErrorMessage(err, "Failed to load timeline"));
    } finally {
      setTimelineLoading(false);
    }
  }

  async function reloadMembers() {
    setMembersLoading(true);
    setMembersError(null);
    try {
      const list = await bffFetch<Member[]>(`/v1/projects/${projectId}/members`);
      setMembers(list);
    } catch (err) {
      setMembersError(getErrorMessage(err, "Failed to load members"));
    } finally {
      setMembersLoading(false);
    }
  }

  async function reloadAll() {
    setProjectLoading(true);
    setProjectError(null);
    try {
      const loadedProject = await bffFetch<Project>(`/v1/projects/${projectId}`);
      setProject(loadedProject);
      await Promise.all([
        reloadPermits(),
        reloadToday(loadedProject.timezone),
        reloadTimeline(),
        reloadMembers(),
      ]);
    } catch (err) {
      setProjectError(getErrorMessage(err, "Failed to load project"));
    } finally {
      setProjectLoading(false);
    }
  }

  async function handleLoadMoreTimeline() {
    if (!nextBefore) return;
    setLoadingMore(true);
    setLoadMoreError(null);
    try {
      const resp = await bffFetch<TimelineResponse>(
        `/v1/projects/${projectId}/timeline?before=${encodeURIComponent(
          nextBefore
        )}&days=7`
      );
      setTimelineDays((prev) => {
        const existing = prev ?? [];
        const seen = new Set(existing.map((d) => d.log_date));
        const merged = [...existing];
        for (const day of resp.days) {
          if (!seen.has(day.log_date)) {
            merged.push(day);
          }
        }
        return merged;
      });
      setNextBefore(resp.next_before);
    } catch (err) {
      setLoadMoreError(getErrorMessage(err, "Failed to load older days"));
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleDeletePermit(permitId: string) {
    await bffFetch<void>(`/v1/permits/${permitId}`, { method: "DELETE" });
    setPermits((prev) => (prev ? prev.filter((p) => p.id !== permitId) : prev));
  }

  async function handleRetryExtraction(logId: string) {
    const queued = await bffFetch<ExtractQueueResponse>("/v1/logs/extract", {
      method: "POST",
      body: JSON.stringify({ log_id: logId }),
    });

    const patchLog = (day: DailyReport): DailyReport => ({
      ...day,
      logs: day.logs.map((l) =>
        l.id === logId
          ? {
              ...l,
              extraction_status: queued.extraction_status,
              extraction_error: null,
            }
          : l
      ),
    });

    setTimelineDays((prev) => (prev ? prev.map(patchLog) : prev));
    setTodayReport((prev) => (prev ? patchLog(prev) : prev));
  }

  async function handleEditLog(logId: string, notes: string) {
    const updated = await bffFetch<SiteLog>(`/v1/logs/${logId}`, {
      method: "PATCH",
      body: JSON.stringify({ notes }),
    });
    const replaceLog = (day: DailyReport): DailyReport => ({
      ...day,
      logs: day.logs.map((l) => (l.id === logId ? updated : l)),
    });
    setTimelineDays((prev) => (prev ? prev.map(replaceLog) : prev));
    setTodayReport((prev) => (prev ? replaceLog(prev) : prev));
  }

  async function handleDeleteLog(logId: string) {
    await bffFetch<void>(`/v1/logs/${logId}`, { method: "DELETE" });
    const removeLog = (day: DailyReport): DailyReport => ({
      ...day,
      logs: day.logs.filter((l) => l.id !== logId),
      log_count: Math.max(0, day.log_count - (day.logs.some((l) => l.id === logId) ? 1 : 0)),
    });
    setTimelineDays((prev) =>
      prev ? prev.map(removeLog).filter((d) => d.logs.length > 0) : prev
    );
    setTodayReport((prev) => (prev ? removeLog(prev) : prev));
  }

  async function handleExportTodayPdf() {
    if (!project) return;
    setTodayPdfError(null);
    setExportingTodayPdf(true);
    try {
      await downloadDailyReportPdf(project.id, todayDate);
    } catch (err) {
      setTodayPdfError(err instanceof Error ? err.message : "Failed to export PDF");
    } finally {
      setExportingTodayPdf(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <PortalHeader
        user={user}
        projectBreadcrumb={
          project ? { id: project.id, name: project.name } : undefined
        }
      />

      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6 sm:py-8">
        {projectLoading ? (
          <ProjectDashboardSkeleton />
        ) : !project ? (
          <div className="space-y-4">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-[#475569] hover:text-[#0F172A]"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Portfolio</span>
            </Link>
            <InlineErrorBanner
              title="Project could not be loaded"
              message={projectError ?? "Project not found or inaccessible."}
              onRetry={reloadAll}
              retrying={projectLoading}
            />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Project Header */}
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-[#E2E8F0] pb-4">
              <div className="space-y-2 min-w-0">
                <Link
                  href="/"
                  className="inline-flex items-center gap-1 text-xs font-medium text-[#475569] hover:text-[#0F172A]"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>All Projects</span>
                </Link>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#0F172A]">
                  {project.name}
                </h1>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#475569]">
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3.5 w-3.5 text-[#64748B]" />
                    {project.site_address}
                  </span>
                  <span className="inline-flex items-center gap-1 font-mono">
                    <Clock className="h-3.5 w-3.5 text-[#64748B]" />
                    {project.timezone}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 shrink-0">
                <button
                  type="button"
                  disabled={exportingTodayPdf}
                  onClick={handleExportTodayPdf}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-3.5 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
                >
                  <FileDown className="h-4 w-4" aria-hidden="true" />
                  <span>{exportingTodayPdf ? "Generating PDF..." : "Export Today PDF"}</span>
                </button>
              </div>
            </div>

            {todayPdfError && (
              <InlineErrorBanner
                title="Could not export today's PDF"
                message={todayPdfError}
              />
            )}

            {/* Section Tabs */}
            <div
              role="tablist"
              aria-label="Project sections"
              className="flex items-center gap-2 border-b border-[#E2E8F0] pb-3"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "overview"}
                onClick={() => setActiveTab("overview")}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium cursor-pointer ${
                  activeTab === "overview"
                    ? "border-[#D97706] bg-[#FFFBEB] text-[#92400E]"
                    : "border-[#E2E8F0] bg-[#FFFFFF] text-[#475569] hover:text-[#0F172A]"
                }`}
              >
                <LayoutGrid className="h-4 w-4" />
                <span>Bento &amp; Timeline</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeTab === "team"}
                onClick={() => setActiveTab("team")}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium cursor-pointer ${
                  activeTab === "team"
                    ? "border-[#D97706] bg-[#FFFBEB] text-[#92400E]"
                    : "border-[#E2E8F0] bg-[#FFFFFF] text-[#475569] hover:text-[#0F172A]"
                }`}
              >
                <Users className="h-4 w-4" />
                <span>Team &amp; Settings</span>
                {members && (
                  <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-[#475569]">
                    {members.length}
                  </span>
                )}
              </button>
            </div>

            {activeTab === "overview" ? (
              <div className="space-y-8">
                {/* 5-Tile Bento Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Tile 1: Permits */}
                  <PermitsTile
                    permits={permits}
                    loading={permitsLoading}
                    error={permitsError}
                    isOwner={isOwner}
                    onRetry={reloadPermits}
                    onAdd={() => {
                      setEditingPermit(null);
                      setPermitModalOpen(true);
                    }}
                    onEdit={(permit) => {
                      setEditingPermit(permit);
                      setPermitModalOpen(true);
                    }}
                    onDelete={handleDeletePermit}
                    onViewPhoto={setLightboxImage}
                  />

                  {/* Tiles 2, 3, 4, 5: Today Summary, Blockers, Deliveries, Photo Strip */}
                  <TodayBentoTiles
                    projectId={project.id}
                    timezone={project.timezone}
                    todayDate={todayDate}
                    report={todayReport}
                    loading={todayLoading}
                    error={todayError}
                    onRetry={() => reloadToday(project.timezone)}
                    onViewPhoto={setLightboxImage}
                  />
                </div>

                {/* Reverse-Chronological Day-Grouped Timeline */}
                <TimelineSection
                  projectId={project.id}
                  timezone={project.timezone}
                  currentUser={user}
                  days={timelineDays}
                  nextBefore={nextBefore}
                  loading={timelineLoading}
                  loadingMore={loadingMore}
                  error={timelineError}
                  loadMoreError={loadMoreError}
                  onRetry={reloadTimeline}
                  onLoadMore={handleLoadMoreTimeline}
                  onRetryExtraction={handleRetryExtraction}
                  onEditLog={handleEditLog}
                  onDeleteLog={handleDeleteLog}
                  onViewPhoto={setLightboxImage}
                />
              </div>
            ) : (
              <TeamSettingsPanel
                project={project}
                currentUser={user}
                members={members}
                membersLoading={membersLoading}
                membersError={membersError}
                onRetryMembers={reloadMembers}
                onMembersChange={setMembers}
                onProjectUpdated={(updated) => {
                  const tzChanged = updated.timezone !== project.timezone;
                  setProject(updated);
                  if (tzChanged) {
                    void reloadToday(updated.timezone);
                  }
                }}
              />
            )}
          </div>
        )}
      </main>

      <PermitModal
        open={permitModalOpen}
        projectId={projectId}
        editingPermit={editingPermit}
        onClose={() => setPermitModalOpen(false)}
        onSaved={() => {
          setPermitModalOpen(false);
          void reloadPermits();
        }}
      />

      <PhotoLightbox
        image={lightboxImage}
        onClose={() => setLightboxImage(null)}
      />
    </div>
  );
}
