"use client";

import React, { useState } from "react";
import { AlertCircle, Upload } from "lucide-react";
import type { Permit, PermitInput, PermitPatch, UploadTicket } from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import { Modal } from "@/components/ui/modal";

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

interface PermitModalProps {
  open: boolean;
  projectId: string;
  editingPermit: Permit | null;
  onClose: () => void;
  onSaved: (permit: Permit, isEdit: boolean) => void;
}

export function PermitModal({
  open,
  projectId,
  editingPermit,
  onClose,
  onSaved,
}: PermitModalProps) {
  const [permitName, setPermitName] = useState(
    () => editingPermit?.permit_name ?? ""
  );
  const [authority, setAuthority] = useState(
    () => editingPermit?.authority ?? ""
  );
  const [permitNumber, setPermitNumber] = useState(
    () => editingPermit?.permit_number ?? ""
  );
  const [issueDate, setIssueDate] = useState(
    () => editingPermit?.issue_date ?? ""
  );
  const [expiryDate, setExpiryDate] = useState(
    () => editingPermit?.expiry_date ?? ""
  );
  const [docFile, setDocFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      let savedPermit: Permit;
      const isEdit = Boolean(editingPermit);
      if (editingPermit) {
        const patch: PermitPatch = {
          permit_name: permitName.trim(),
          authority: authority.trim(),
          permit_number: permitNumber.trim() ? permitNumber.trim() : null,
          issue_date: issueDate.trim() ? issueDate.trim() : null,
          expiry_date: expiryDate,
        };
        savedPermit = await bffFetch<Permit>(`/v1/permits/${editingPermit.id}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
      } else {
        const input: PermitInput = {
          permit_name: permitName.trim(),
          authority: authority.trim(),
          permit_number: permitNumber.trim() ? permitNumber.trim() : null,
          issue_date: issueDate.trim() ? issueDate.trim() : null,
          expiry_date: expiryDate,
        };
        savedPermit = await bffFetch<Permit>(
          `/v1/projects/${projectId}/permits`,
          {
            method: "POST",
            body: JSON.stringify(input),
          }
        );
      }

      if (docFile) {
        const allowedTypes = new Set([
          "image/jpeg",
          "image/png",
          "image/webp",
          "application/pdf",
        ]);
        const contentType = allowedTypes.has(docFile.type)
          ? docFile.type
          : "image/jpeg";
        const fileBytes = await docFile.arrayBuffer();
        const sha256 = await sha256Hex(fileBytes);
        const ticket = await bffFetch<UploadTicket>("/v1/media/upload-url", {
          method: "POST",
          body: JSON.stringify({
            kind: "PERMIT_DOC",
            project_id: projectId,
            object_id: savedPermit.id,
            content_type: contentType,
            byte_size: fileBytes.byteLength,
          }),
        });

        const putRes = await fetch(ticket.upload_url, {
          method: ticket.method || "PUT",
          headers: ticket.headers,
          body: fileBytes,
        });
        if (!putRes.ok) {
          throw new Error(`Permit document upload failed (${putRes.status})`);
        }

        await bffFetch<void>("/v1/media/complete", {
          method: "POST",
          body: JSON.stringify({
            kind: "PERMIT_DOC",
            object_id: savedPermit.id,
            ticket_id: ticket.ticket_id ?? undefined,
            sha256,
          }),
        });

        savedPermit = await bffFetch<Permit>(`/v1/permits/${savedPermit.id}`, {
          method: "PATCH",
          body: JSON.stringify({ document_photo_uri: ticket.storage_uri }),
        });
      }

      onSaved(savedPermit, isEdit);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save permit"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editingPermit ? "Edit Permit" : "Add Site Permit"}
      subtitle="Permit status (ACTIVE, EXPIRING_SOON, EXPIRED) is derived automatically from expiry date in project timezone."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-[#FECACA] bg-[#FEF2F2] p-3 text-sm text-[#991B1B]"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-[#DC2626] mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div className="space-y-1.5">
          <label
            htmlFor="permit-name"
            className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
          >
            Permit Name
          </label>
          <input
            id="permit-name"
            type="text"
            required
            value={permitName}
            onChange={(e) => setPermitName(e.target.value)}
            placeholder="e.g. CDA Building Plan Approval"
            className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label
              htmlFor="permit-authority"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Issuing Authority
            </label>
            <input
              id="permit-authority"
              type="text"
              required
              value={authority}
              onChange={(e) => setAuthority(e.target.value)}
              placeholder="e.g. CDA / LDA / Municipal Corp"
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="permit-number"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Permit Number (Optional)
            </label>
            <input
              id="permit-number"
              type="text"
              value={permitNumber}
              onChange={(e) => setPermitNumber(e.target.value)}
              placeholder="CDA-2026-4418"
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label
              htmlFor="issue-date"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Issue Date (Optional)
            </label>
            <input
              id="issue-date"
              type="date"
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm tabular-nums text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="expiry-date"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Expiry Date
            </label>
            <input
              id="expiry-date"
              type="date"
              required
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm tabular-nums text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="permit-doc"
            className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
          >
            Permit Scan / Photo (Optional, JPEG/PNG/WebP/PDF)
          </label>
          <label className="flex items-center justify-between rounded-md border border-dashed border-[#CBD5E1] bg-[#F8FAFC] px-3 py-2 text-xs text-[#475569] hover:border-[#D97706] cursor-pointer">
            <span className="inline-flex items-center gap-2 truncate">
              <Upload className="h-4 w-4 text-[#D97706] shrink-0" />
              <span className="truncate">
                {docFile ? docFile.name : "Choose permit scan file..."}
              </span>
            </span>
            <input
              id="permit-doc"
              type="file"
              accept="image/jpeg,image/png,image/webp,application/pdf"
              onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
              className="sr-only"
            />
          </label>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-[#E2E8F0] pt-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-4 py-2 text-sm font-medium text-[#475569] hover:bg-[#F8FAFC] cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-[#D97706] px-4 py-2 text-sm font-semibold text-[#FFFFFF] hover:bg-[#B45309] disabled:opacity-50 cursor-pointer"
          >
            {submitting
              ? "Saving..."
              : editingPermit
              ? "Save Changes"
              : "Add Permit"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
