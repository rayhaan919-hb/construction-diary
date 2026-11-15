"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Mic,
  Package,
  Pencil,
  RefreshCw,
  Trash2,
  UserCheck,
  Users,
} from "lucide-react";
import type { SiteLog } from "@/lib/types";
import {
  formatDurationMs,
  formatTimeInZone,
  getLanguageLabel,
  getTextDirection,
} from "@/lib/format";
import { ExtractionStatusBadge } from "@/components/ui/status-badges";
import type { LightboxImage } from "@/components/ui/photo-lightbox";

interface LogNoteCardProps {
  log: SiteLog;
  timezone: string;
  canManage?: boolean;
  onRetryExtraction: (logId: string) => Promise<void>;
  onEditLog?: (logId: string, notes: string) => Promise<void>;
  onDeleteLog?: (logId: string) => Promise<void>;
  onViewPhoto: (image: LightboxImage) => void;
}

export function LogNoteCard({
  log,
  timezone,
  canManage = false,
  onRetryExtraction,
  onEditLog,
  onDeleteLog,
  onViewPhoto,
}: LogNoteCardProps) {
  const [showTranscript, setShowTranscript] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [editingNotes, setEditingNotes] = useState(false);
  const [draftNotes, setDraftNotes] = useState(log.notes ?? "");
  const [savingNotes, setSavingNotes] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const summary = log.structured_summary;
  const photos = log.photos ?? [];
  const timeFormatted = formatTimeInZone(log.recorded_at, timezone);
  const transcriptDir = getTextDirection(log.detected_language, log.transcript);

  async function handleSaveNotes(e: React.FormEvent) {
    e.preventDefault();
    if (!onEditLog) return;
    setActionError(null);
    setSavingNotes(true);
    try {
      await onEditLog(log.id, draftNotes);
      setEditingNotes(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save note");
    } finally {
      setSavingNotes(false);
    }
  }

  async function handleConfirmDelete() {
    if (!onDeleteLog) return;
    setActionError(null);
    setDeleting(true);
    try {
      await onDeleteLog(log.id);
      setConfirmDelete(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to delete log");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRetry() {
    setRetryError(null);
    setRetrying(true);
    try {
      await onRetryExtraction(log.id);
    } catch (err) {
      setRetryError(
        err instanceof Error ? err.message : "Could not queue extraction"
      );
    } finally {
      setRetrying(false);
    }
  }

  return (
    <article className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] p-4 space-y-3">
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-0.5 font-mono text-xs font-semibold tabular-nums text-[#0F172A]">
            <Clock className="h-3 w-3 text-[#64748B]" aria-hidden="true" />
            {timeFormatted}
          </span>
          <span className="text-sm font-medium text-[#0F172A]">
            {log.author_name ?? "Site Supervisor"}
          </span>
          <ExtractionStatusBadge status={log.extraction_status} />
          {log.edited_by_human && (
            <span className="inline-flex items-center gap-1 rounded border border-[#BFDBFE] bg-[#EFF6FF] px-2 py-0.5 font-mono text-[11px] font-medium text-[#1D4ED8]">
              <UserCheck className="h-3 w-3" aria-hidden="true" />
              Edited
            </span>
          )}
          {log.audio_duration_ms !== null && log.audio_duration_ms !== undefined && (
            <span className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-0.5 font-mono text-[11px] tabular-nums text-[#475569]">
              <Mic className="h-3 w-3 text-[#D97706]" aria-hidden="true" />
              {formatDurationMs(log.audio_duration_ms)}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {summary &&
            summary.labor_count !== null &&
            summary.labor_count !== undefined && (
              <span className="inline-flex items-center gap-1.5 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 font-mono text-xs font-semibold tabular-nums text-[#0F172A]">
                <Users className="h-3.5 w-3.5 text-[#D97706]" aria-hidden="true" />
                <span>{summary.labor_count} workers</span>
              </span>
            )}
          {canManage && onEditLog && (
            <button
              type="button"
              onClick={() => {
                setDraftNotes(log.notes ?? "");
                setEditingNotes((v) => !v);
              }}
              aria-label="Edit site note"
              className="rounded border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A] cursor-pointer"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
          {canManage && onDeleteLog && (
            confirmDelete ? (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={deleting}
                  onClick={handleConfirmDelete}
                  className="rounded border border-[#FECACA] bg-[#DC2626] px-2 py-1 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B91C1C] disabled:opacity-50 cursor-pointer"
                >
                  {deleting ? "..." : "Delete"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-1 text-xs text-[#475569] hover:bg-[#F8FAFC] cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                aria-label="Delete site note"
                className="rounded border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:border-[#FECACA] hover:bg-[#FEF2F2] hover:text-[#DC2626] cursor-pointer"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )
          )}
        </div>
      </div>

      {actionError && (
        <p role="alert" className="text-xs font-medium text-[#DC2626]">
          {actionError}
        </p>
      )}

      {/* Extraction Failed Banner */}
      {log.extraction_status === "FAILED" && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-md border border-[#FECACA] bg-[#FEF2F2] p-3 text-xs">
          <div className="space-y-0.5 text-[#991B1B]">
            <p className="font-semibold">Voice extraction failed</p>
            <p>{log.extraction_error || "Gemini extraction encountered an error."}</p>
            {retryError && <p className="font-medium">{retryError}</p>}
          </div>
          <button
            type="button"
            onClick={handleRetry}
            disabled={retrying}
            className="inline-flex items-center gap-1.5 rounded border border-[#FCA5A5] bg-[#FFFFFF] px-3 py-1.5 text-xs font-semibold text-[#991B1B] hover:bg-[#FEE2E2] disabled:opacity-50 shrink-0 cursor-pointer"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${retrying ? "animate-spin" : ""}`}
            />
            <span>{retrying ? "Queueing..." : "Retry Extraction"}</span>
          </button>
        </div>
      )}

      {/* Structured English Summary */}
      {summary ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-3 space-y-1.5">
            <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#475569]">
              <CheckCircle2 className="h-3.5 w-3.5 text-[#059669]" />
              Tasks Completed
            </h4>
            {summary.tasks_completed.length === 0 ? (
              <p className="text-xs text-[#64748B]">None mentioned</p>
            ) : (
              <ul className="space-y-1 text-xs text-[#0F172A]">
                {summary.tasks_completed.map((t, i) => (
                  <li key={i} className="leading-snug">
                    • {t}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-3 space-y-1.5">
            <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#475569]">
              <Package className="h-3.5 w-3.5 text-[#D97706]" />
              Material Deliveries
            </h4>
            {summary.material_deliveries.length === 0 ? (
              <p className="text-xs text-[#64748B]">None mentioned</p>
            ) : (
              <ul className="space-y-1 text-xs text-[#0F172A]">
                {summary.material_deliveries.map((m, i) => (
                  <li key={i} className="leading-snug">
                    • {m}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-3 space-y-1.5">
            <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-[#475569]">
              <AlertTriangle className="h-3.5 w-3.5 text-[#EA580C]" />
              Blockers
            </h4>
            {summary.blockers.length === 0 ? (
              <p className="text-xs text-[#64748B]">No blockers</p>
            ) : (
              <ul className="space-y-1 text-xs text-[#9A3412]">
                {summary.blockers.map((b, i) => (
                  <li key={i} className="leading-snug font-medium">
                    • {b}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : (
        log.extraction_status !== "FAILED" && (
          <p className="text-xs text-[#64748B]">
            {log.audio_uri
              ? `Audio status: ${log.audio_upload_status}. AI extraction ${log.extraction_status.toLowerCase()}.`
              : "Typed site note (no voice recording attached)."}
          </p>
        )
      )}

      {/* Audio Player when signed URL is available */}
      {log.audio_url && (
        <div className="rounded border border-[#E2E8F0] bg-[#F8FAFC] p-2">
          <audio
            controls
            preload="none"
            src={log.audio_url}
            className="h-8 w-full"
          >
            Your browser does not support audio playback.
          </audio>
        </div>
      )}

      {/* Optional Supervisor Typed Note (inline editable) */}
      {editingNotes ? (
        <form onSubmit={handleSaveNotes} className="space-y-2 rounded border border-[#E2E8F0] bg-[#F8FAFC] p-3">
          <textarea
            rows={3}
            value={draftNotes}
            onChange={(e) => setDraftNotes(e.target.value)}
            placeholder="Update typed supervisor field notes..."
            className="w-full rounded-md border border-[#CBD5E1] bg-[#FFFFFF] px-3 py-2 text-xs text-[#0F172A] focus:border-[#D97706] focus:outline-none"
          />
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setEditingNotes(false)}
              className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2.5 py-1 text-xs text-[#475569] hover:bg-[#F8FAFC] cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={savingNotes}
              className="rounded bg-[#D97706] px-3 py-1 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
            >
              {savingNotes ? "Saving..." : "Save Note"}
            </button>
          </div>
        </form>
      ) : (
        log.notes && (
          <div className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-xs text-[#334155]">
            <span className="font-semibold text-[#0F172A]">Field Note: </span>
            <span dir="auto">{log.notes}</span>
          </div>
        )
      )}

      {/* Transcript Toggle (with dir="auto" for Urdu/Arabic) */}
      {log.transcript && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setShowTranscript((prev) => !prev)}
            className="inline-flex items-center gap-1.5 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 text-xs font-medium text-[#475569] hover:text-[#0F172A] cursor-pointer"
          >
            <FileText className="h-3.5 w-3.5 text-[#D97706]" />
            <span>
              {showTranscript ? "Hide" : "View"} Original Transcript (
              {getLanguageLabel(log.detected_language)})
            </span>
            {showTranscript ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {showTranscript && (
            <div className="rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3">
              <p
                dir="auto"
                lang={
                  log.detected_language &&
                  log.detected_language !== "mixed" &&
                  log.detected_language !== "unknown"
                    ? log.detected_language
                    : undefined
                }
                className={
                  transcriptDir === "rtl"
                    ? "font-arabic text-base leading-relaxed text-[#0F172A] text-right"
                    : "text-sm leading-relaxed text-[#0F172A]"
                }
              >
                {log.transcript}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Photo Thumbnails */}
      {photos.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {photos.map((photo) =>
            photo.url ? (
              <button
                key={photo.id}
                type="button"
                onClick={() =>
                  onViewPhoto({
                    url: photo.url as string,
                    title: `Site Photo · ${timeFormatted}`,
                    meta: `${log.author_name ?? "Supervisor"} · ${log.log_date}`,
                  })
                }
                className="relative h-16 w-16 overflow-hidden rounded border border-[#E2E8F0] bg-[#F8FAFC] hover:border-[#D97706] cursor-pointer"
              >
                <img
                  src={photo.url}
                  alt={`Log photo ${timeFormatted}`}
                  className="h-full w-full object-cover"
                />
              </button>
            ) : (
              <div
                key={photo.id}
                className="flex h-16 w-16 flex-col items-center justify-center rounded border border-[#E2E8F0] bg-[#F8FAFC] p-1 text-center font-mono text-[10px] text-[#64748B]"
              >
                <Camera className="h-3.5 w-3.5 mb-0.5" />
                <span>{photo.upload_status}</span>
              </div>
            )
          )}
        </div>
      )}
    </article>
  );
}
