"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Plus, RefreshCw } from "lucide-react";
import type { ProjectSummary, User } from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import { PortalHeader } from "@/components/layout/portal-header";
import { EmptyState, InlineErrorBanner } from "@/components/ui/states";
import { ProjectCard } from "./project-card";
import { CreateProjectModal } from "./create-project-modal";
import { PortfolioSkeleton } from "./portfolio-skeleton";

interface PortfolioViewProps {
  user: User | null;
  initialProjects: ProjectSummary[] | null;
  initialError: string | null;
}

export function PortfolioView({
  user,
  initialProjects,
  initialError,
}: PortfolioViewProps) {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(initialProjects);
  const [error, setError] = useState<string | null>(initialError);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  const isOwner = user?.role === "OWNER";

  async function reloadProjects() {
    setLoading(true);
    setError(null);
    try {
      const list = await bffFetch<ProjectSummary[]>("/v1/projects");
      setProjects(list);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load projects"));
    } finally {
      setLoading(false);
    }
  }

  const totalSites = projects?.length ?? 0;
  const permitAlerts =
    projects?.filter(
      (p) => p.permit_health === "WARN" || p.permit_health === "EXPIRED"
    ).length ?? 0;
  const totalOpenBlockers =
    projects?.reduce((acc, p) => acc + p.open_blockers_count, 0) ?? 0;

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <PortalHeader user={user} />

      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6 sm:py-8">
        {loading && !projects ? (
          <PortfolioSkeleton />
        ) : (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold tracking-tight text-[#0F172A]">
                  Project Portfolio
                </h1>
                <p className="text-sm text-[#475569]">
                  Permit compliance, today&apos;s labor rollups, and active site blockers.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={reloadProjects}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm font-medium text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A] disabled:opacity-50 cursor-pointer"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
                    aria-hidden="true"
                  />
                  <span>Refresh</span>
                </button>
                {isOwner && (
                  <button
                    type="button"
                    onClick={() => setCreateOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-3.5 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
                  >
                    <Plus className="h-4 w-4" aria-hidden="true" />
                    <span>New Project</span>
                  </button>
                )}
              </div>
            </div>

            {error && (
              <InlineErrorBanner
                title="Could not load portfolio"
                message={error}
                onRetry={reloadProjects}
                retrying={loading}
              />
            )}

            {loading ? (
              <PortfolioSkeleton />
            ) : projects && projects.length === 0 ? (
              <EmptyState
                icon={<Building2 className="h-5 w-5" />}
                title="No construction projects yet"
                description="Create your first project site to manage permits, invite supervisors, and export daily PDF reports."
                action={
                  isOwner ? (
                    <button
                      type="button"
                      onClick={() => setCreateOpen(true)}
                      className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
                    >
                      <Plus className="h-4 w-4" aria-hidden="true" />
                      <span>New Project</span>
                    </button>
                  ) : undefined
                }
              />
            ) : projects ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                      Active Sites
                    </p>
                    <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-[#0F172A]">
                      {totalSites}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                      Sites Needing Permit Action
                    </p>
                    <p
                      className={`mt-1 font-mono text-2xl font-bold tabular-nums ${
                        permitAlerts > 0 ? "text-[#EA580C]" : "text-[#059669]"
                      }`}
                    >
                      {permitAlerts}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                      Open Blockers Today
                    </p>
                    <p
                      className={`mt-1 font-mono text-2xl font-bold tabular-nums ${
                        totalOpenBlockers > 0 ? "text-[#DC2626]" : "text-[#059669]"
                      }`}
                    >
                      {totalOpenBlockers}
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {projects.map((summary) => (
                    <ProjectCard key={summary.project.id} summary={summary} />
                  ))}
                </div>
              </>
            ) : null}
          </div>
        )}
      </main>

      <CreateProjectModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(project) => {
          setCreateOpen(false);
          router.push(`/projects/${project.id}`);
          router.refresh();
        }}
      />
    </div>
  );
}
