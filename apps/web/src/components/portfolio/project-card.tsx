import React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Clock, MapPin, Users } from "lucide-react";
import type { ProjectSummary } from "@/lib/types";
import { formatCountdown, formatDateShort, formatTimeInZone } from "@/lib/format";
import { PermitHealthBadge } from "@/components/ui/status-badges";

export function ProjectCard({ summary }: { summary: ProjectSummary }) {
  const { project, today, permit_health, next_expiring_permit, open_blockers_count } =
    summary;

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group flex flex-col justify-between rounded-lg border border-[#E2E8F0] bg-[#FFFFFF] p-4 transition-colors hover:border-[#D97706] focus:outline-none focus:ring-2 focus:ring-[#D97706]/30"
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <h2 className="truncate text-base font-semibold text-[#0F172A] group-hover:text-[#B45309]">
              {project.name}
            </h2>
            <p className="flex items-start gap-1.5 text-xs text-[#475569]">
              <MapPin className="h-3.5 w-3.5 shrink-0 text-[#64748B] mt-0.5" aria-hidden="true" />
              <span className="line-clamp-2">{project.site_address}</span>
            </p>
          </div>
          <div className="shrink-0">
            <PermitHealthBadge health={permit_health} />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] px-3 py-2 text-xs">
          {next_expiring_permit ? (
            <>
              <span className="truncate font-medium text-[#0F172A]">
                Next: {next_expiring_permit.permit_name}
              </span>
              <span
                className={`shrink-0 font-mono font-semibold tabular-nums ${
                  next_expiring_permit.days_to_expiry < 0
                    ? "text-[#DC2626]"
                    : next_expiring_permit.days_to_expiry <= 14
                    ? "text-[#EA580C]"
                    : "text-[#059669]"
                }`}
              >
                {formatCountdown(next_expiring_permit.days_to_expiry)}
              </span>
            </>
          ) : (
            <span className="text-[#64748B]">No active permits recorded</span>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] p-2.5">
            <div className="flex items-center gap-1 text-[11px] font-medium text-[#64748B]">
              <Users className="h-3 w-3" aria-hidden="true" />
              <span>Labor</span>
            </div>
            <p className="mt-1 font-mono text-lg font-bold tabular-nums text-[#0F172A]">
              {today.labor_max !== null && today.labor_max !== undefined
                ? today.labor_max
                : "—"}
            </p>
          </div>

          <div className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] p-2.5">
            <div className="flex items-center gap-1 text-[11px] font-medium text-[#64748B]">
              <Clock className="h-3 w-3" aria-hidden="true" />
              <span>Logs</span>
            </div>
            <p className="mt-1 font-mono text-lg font-bold tabular-nums text-[#0F172A]">
              {today.log_count}
            </p>
          </div>

          <div className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] p-2.5">
            <div className="flex items-center gap-1 text-[11px] font-medium text-[#64748B]">
              <AlertTriangle className="h-3 w-3" aria-hidden="true" />
              <span>Blockers</span>
            </div>
            <p
              className={`mt-1 font-mono text-lg font-bold tabular-nums ${
                open_blockers_count > 0 ? "text-[#EA580C]" : "text-[#059669]"
              }`}
            >
              {open_blockers_count}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-[#E2E8F0] pt-3 text-xs text-[#64748B]">
        <div className="flex items-center gap-2 font-mono tabular-nums min-w-0 truncate">
          <span>{formatDateShort(today.log_date)}</span>
          <span>·</span>
          <span>
            {today.last_log_at
              ? `Last ${formatTimeInZone(today.last_log_at, project.timezone)}`
              : "No logs today"}
          </span>
        </div>
        <span className="inline-flex items-center gap-1 font-medium text-[#D97706] shrink-0">
          <span>Open</span>
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </div>
    </Link>
  );
}
