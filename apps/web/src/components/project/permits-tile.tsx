"use client";

import React, { useState } from "react";
import {
  FileCheck2,
  Image as ImageIcon,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import type { Permit } from "@/lib/types";
import { formatCountdown, formatDateShort } from "@/lib/format";
import {
  EmptyState,
  InlineErrorBanner,
  SkeletonBlock,
} from "@/components/ui/states";
import { PermitStatusBadge } from "@/components/ui/status-badges";
import type { LightboxImage } from "@/components/ui/photo-lightbox";

interface PermitsTileProps {
  permits: Permit[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onAdd: () => void;
  onEdit: (permit: Permit) => void;
  onDelete: (permitId: string) => Promise<void>;
  onViewPhoto: (image: LightboxImage) => void;
}

export function PermitsTile({
  permits,
  loading,
  error,
  onRetry,
  onAdd,
  onEdit,
  onDelete,
  onViewPhoto,
}: PermitsTileProps) {
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleConfirmDelete(permitId: string) {
    setDeleteError(null);
    setDeletingId(permitId);
    try {
      await onDelete(permitId);
      setConfirmDeleteId(null);
    } catch (err) {
      setDeleteError(
        err instanceof Error ? err.message : "Failed to delete permit"
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="flex flex-col rounded-lg border border-[#E2E8F0] bg-[#FFFFFF]">
      <div className="flex items-center justify-between gap-3 border-b border-[#E2E8F0] px-4 py-3">
        <div className="flex items-center gap-2">
          <FileCheck2 className="h-4 w-4 text-[#D97706]" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-[#0F172A]">
            Site Permits &amp; Compliance
          </h2>
          {permits && (
            <span className="rounded border border-[#E2E8F0] bg-[#F8FAFC] px-1.5 py-0.5 font-mono text-xs tabular-nums text-[#475569]">
              {permits.length}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex items-center gap-1 rounded-md bg-[#D97706] px-2.5 py-1.5 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          <span>Add Permit</span>
        </button>
      </div>

      <div className="flex-1 p-4 space-y-3">
        {deleteError && (
          <InlineErrorBanner
            title="Could not delete permit"
            message={deleteError}
          />
        )}

        {loading ? (
          <div className="space-y-2.5" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md border border-[#E2E8F0] p-3"
              >
                <div className="space-y-1.5">
                  <SkeletonBlock className="h-4 w-44" />
                  <SkeletonBlock className="h-3 w-32" />
                </div>
                <SkeletonBlock className="h-6 w-24" />
              </div>
            ))}
          </div>
        ) : error ? (
          <InlineErrorBanner
            title="Failed to load permits"
            message={error}
            onRetry={onRetry}
          />
        ) : !permits || permits.length === 0 ? (
          <EmptyState
            compact
            icon={<FileCheck2 className="h-5 w-5" />}
            title="No permits recorded"
            description="Track municipal approvals and safety certificates to receive expiry countdown alerts."
            action={
              <button
                type="button"
                onClick={onAdd}
                className="inline-flex items-center gap-1.5 rounded-md bg-[#D97706] px-3.5 py-2 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B45309] cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Add First Permit</span>
              </button>
            }
          />
        ) : (
          <div className="divide-y divide-[#E2E8F0] rounded-md border border-[#E2E8F0]">
            {permits.map((permit) => {
              const countdownColor =
                permit.days_to_expiry < 0
                  ? "text-[#DC2626]"
                  : permit.days_to_expiry <= 14
                  ? "text-[#EA580C]"
                  : "text-[#059669]";

              return (
                <div
                  key={permit.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-[#FFFFFF] first:rounded-t-md last:rounded-b-md"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-[#0F172A]">
                        {permit.permit_name}
                      </span>
                      <PermitStatusBadge status={permit.status} />
                    </div>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#475569]">
                      <span>{permit.authority}</span>
                      {permit.permit_number && (
                        <span className="font-mono text-[#0F172A]">
                          #{permit.permit_number}
                        </span>
                      )}
                      <span className="font-mono tabular-nums">
                        Exp: {formatDateShort(permit.expiry_date)}
                      </span>
                      <span
                        className={`font-mono font-semibold tabular-nums ${countdownColor}`}
                      >
                        ({formatCountdown(permit.days_to_expiry)})
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {permit.document_photo_url && (
                      <button
                        type="button"
                        onClick={() =>
                          onViewPhoto({
                            url: permit.document_photo_url as string,
                            title: permit.permit_name,
                            meta: `${permit.authority}${
                              permit.permit_number
                                ? ` · #${permit.permit_number}`
                                : ""
                            }`,
                          })
                        }
                        className="inline-flex items-center gap-1 rounded border border-[#E2E8F0] bg-[#F8FAFC] px-2 py-1 text-xs font-medium text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
                      >
                        <ImageIcon className="h-3.5 w-3.5 text-[#D97706]" />
                        <span>Doc</span>
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => onEdit(permit)}
                      aria-label={`Edit ${permit.permit_name}`}
                      className="rounded border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A] cursor-pointer"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>

                    {confirmDeleteId === permit.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          disabled={deletingId === permit.id}
                          onClick={() => handleConfirmDelete(permit.id)}
                          className="rounded border border-[#FECACA] bg-[#DC2626] px-2 py-1 text-xs font-semibold text-[#FFFFFF] hover:bg-[#B91C1C] disabled:opacity-50 cursor-pointer"
                        >
                          {deletingId === permit.id ? "..." : "Confirm"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                          className="rounded border border-[#E2E8F0] bg-[#FFFFFF] px-2 py-1 text-xs text-[#475569] hover:bg-[#F8FAFC] cursor-pointer"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(permit.id)}
                        aria-label={`Delete ${permit.permit_name}`}
                        className="rounded border border-[#E2E8F0] bg-[#FFFFFF] p-1.5 text-[#475569] hover:border-[#FECACA] hover:bg-[#FEF2F2] hover:text-[#DC2626] cursor-pointer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
