import React from "react";

type PermitHealthValue = "OK" | "WARN" | "EXPIRED" | "NONE";
type PermitStatusValue = "ACTIVE" | "EXPIRING_SOON" | "EXPIRED";
type ExtractionStatusValue =
  | "NOT_STARTED"
  | "PENDING"
  | "PROCESSING"
  | "DONE"
  | "FAILED";

const PERMIT_HEALTH_STYLE: Record<
  PermitHealthValue,
  { label: string; bg: string; border: string; text: string; dot: string }
> = {
  OK: {
    label: "Permits OK",
    bg: "bg-[#ECFDF5]",
    border: "border-[#A7F3D0]",
    text: "text-[#059669]",
    dot: "bg-[#059669]",
  },
  WARN: {
    label: "Expiring Soon",
    bg: "bg-[#FFF7ED]",
    border: "border-[#FED7AA]",
    text: "text-[#EA580C]",
    dot: "bg-[#EA580C]",
  },
  EXPIRED: {
    label: "Permit Expired",
    bg: "bg-[#FEF2F2]",
    border: "border-[#FECACA]",
    text: "text-[#DC2626]",
    dot: "bg-[#DC2626]",
  },
  NONE: {
    label: "No Permits",
    bg: "bg-[#F1F5F9]",
    border: "border-[#E2E8F0]",
    text: "text-[#475569]",
    dot: "bg-[#64748B]",
  },
};

export function PermitHealthBadge({ health }: { health: PermitHealthValue }) {
  const cfg = PERMIT_HEALTH_STYLE[health];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium ${cfg.bg} ${cfg.border} ${cfg.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} aria-hidden="true" />
      <span>{cfg.label}</span>
    </span>
  );
}

const PERMIT_STATUS_STYLE: Record<
  PermitStatusValue,
  { label: string; bg: string; border: string; text: string }
> = {
  ACTIVE: {
    label: "ACTIVE",
    bg: "bg-[#ECFDF5]",
    border: "border-[#A7F3D0]",
    text: "text-[#059669]",
  },
  EXPIRING_SOON: {
    label: "EXPIRING SOON",
    bg: "bg-[#FFF7ED]",
    border: "border-[#FED7AA]",
    text: "text-[#EA580C]",
  },
  EXPIRED: {
    label: "EXPIRED",
    bg: "bg-[#FEF2F2]",
    border: "border-[#FECACA]",
    text: "text-[#DC2626]",
  },
};

export function PermitStatusBadge({ status }: { status: PermitStatusValue }) {
  const cfg = PERMIT_STATUS_STYLE[status];
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-tight ${cfg.bg} ${cfg.border} ${cfg.text}`}
    >
      {cfg.label}
    </span>
  );
}

const EXTRACTION_STYLE: Record<
  ExtractionStatusValue,
  { label: string; bg: string; border: string; text: string }
> = {
  DONE: {
    label: "EXTRACTED",
    bg: "bg-[#ECFDF5]",
    border: "border-[#A7F3D0]",
    text: "text-[#059669]",
  },
  PROCESSING: {
    label: "PROCESSING",
    bg: "bg-[#FFFBEB]",
    border: "border-[#FDE68A]",
    text: "text-[#D97706]",
  },
  PENDING: {
    label: "PENDING AI",
    bg: "bg-[#FFFBEB]",
    border: "border-[#FDE68A]",
    text: "text-[#D97706]",
  },
  NOT_STARTED: {
    label: "NOTE ONLY",
    bg: "bg-[#F1F5F9]",
    border: "border-[#E2E8F0]",
    text: "text-[#475569]",
  },
  FAILED: {
    label: "FAILED",
    bg: "bg-[#FEF2F2]",
    border: "border-[#FECACA]",
    text: "text-[#DC2626]",
  },
};

export function ExtractionStatusBadge({
  status,
}: {
  status: ExtractionStatusValue;
}) {
  const cfg = EXTRACTION_STYLE[status];
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 font-mono text-[11px] font-medium ${cfg.bg} ${cfg.border} ${cfg.text}`}
    >
      {cfg.label}
    </span>
  );
}
