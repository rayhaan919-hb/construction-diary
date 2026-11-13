import React from "react";
import { SkeletonBlock } from "@/components/ui/states";

export function PortfolioSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading projects">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-2">
          <SkeletonBlock className="h-7 w-48" />
          <SkeletonBlock className="h-4 w-72" />
        </div>
        <div className="flex items-center gap-2">
          <SkeletonBlock className="h-9 w-24" />
          <SkeletonBlock className="h-9 w-32" />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-2"
          >
            <SkeletonBlock className="h-3 w-24" />
            <SkeletonBlock className="h-7 w-16" />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[0, 1, 2, 3, 4, 5].map((idx) => (
          <div
            key={idx}
            className="flex h-[242px] flex-col justify-between rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4"
          >
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1.5 flex-1">
                  <SkeletonBlock className="h-5 w-40" />
                  <SkeletonBlock className="h-3.5 w-52" />
                </div>
                <SkeletonBlock className="h-5 w-24" />
              </div>
              <SkeletonBlock className="h-9 w-full" />
              <div className="grid grid-cols-3 gap-2">
                <SkeletonBlock className="h-16 w-full" />
                <SkeletonBlock className="h-16 w-full" />
                <SkeletonBlock className="h-16 w-full" />
              </div>
            </div>
            <div className="flex items-center justify-between border-t border-[#E2E8F0] pt-3">
              <SkeletonBlock className="h-3.5 w-36" />
              <SkeletonBlock className="h-3.5 w-12" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
