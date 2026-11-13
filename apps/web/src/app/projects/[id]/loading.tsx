import React from "react";
import { PortalHeader } from "@/components/layout/portal-header";
import { ProjectDashboardSkeleton } from "@/components/project/project-dashboard-skeleton";

export default function ProjectLoading() {
  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <PortalHeader />
      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6 sm:py-8">
        <ProjectDashboardSkeleton />
      </main>
    </div>
  );
}
