import React from "react";
import { SkeletonBlock } from "@/components/ui/states";

export function ProjectDashboardSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading project dashboard">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E2E8F0] pb-4">
        <div className="space-y-2">
          <SkeletonBlock className="h-7 w-64" />
          <SkeletonBlock className="h-4 w-96" />
        </div>
        <div className="flex items-center gap-2">
          <SkeletonBlock className="h-9 w-36" />
          <SkeletonBlock className="h-9 w-32" />
        </div>
      </div>

      <div className="flex gap-2">
        <SkeletonBlock className="h-9 w-40" />
        <SkeletonBlock className="h-9 w-36" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="h-[320px] rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <SkeletonBlock className="h-5 w-48" />
          <SkeletonBlock className="h-16 w-full" />
          <SkeletonBlock className="h-16 w-full" />
          <SkeletonBlock className="h-16 w-full" />
        </div>
        <div className="h-[320px] rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
          <SkeletonBlock className="h-5 w-44" />
          <div className="grid grid-cols-2 gap-3">
            <SkeletonBlock className="h-20 w-full" />
            <SkeletonBlock className="h-20 w-full" />
          </div>
          <SkeletonBlock className="h-4 w-56" />
          <SkeletonBlock className="h-4 w-48" />
        </div>
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4">
          <SkeletonBlock className="h-44 w-full rounded-lg" />
          <SkeletonBlock className="h-44 w-full rounded-lg" />
          <SkeletonBlock className="h-44 w-full rounded-lg" />
        </div>
      </div>

      <div className="h-56 rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
        <SkeletonBlock className="h-6 w-52" />
        <SkeletonBlock className="h-32 w-full" />
      </div>
    </div>
  );
}
