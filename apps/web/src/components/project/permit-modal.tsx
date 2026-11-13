"use client";

import React, { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import type { Permit, PermitInput, PermitPatch } from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import { Modal } from "@/components/ui/modal";

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
  const [permitName, setPermitName] = useState("");
  const [authority, setAuthority] = useState("");
  const [permitNumber, setPermitNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    if (editingPermit) {
      setPermitName(editingPermit.permit_name);
      setAuthority(editingPermit.authority);
      setPermitNumber(editingPermit.permit_number ?? "");
      setIssueDate(editingPermit.issue_date ?? "");
      setExpiryDate(editingPermit.expiry_date);
    } else {
      setPermitName("");
      setAuthority("");
      setPermitNumber("");
      setIssueDate("");
      setExpiryDate("");
    }
  }, [open, editingPermit]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (editingPermit) {
        const patch: PermitPatch = {
          permit_name: permitName.trim(),
          authority: authority.trim(),
          permit_number: permitNumber.trim() ? permitNumber.trim() : null,
          issue_date: issueDate.trim() ? issueDate.trim() : null,
          expiry_date: expiryDate,
        };
        const updated = await bffFetch<Permit>(`/v1/permits/${editingPermit.id}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
        onSaved(updated, true);
      } else {
        const input: PermitInput = {
          permit_name: permitName.trim(),
          authority: authority.trim(),
          permit_number: permitNumber.trim() ? permitNumber.trim() : null,
          issue_date: issueDate.trim() ? issueDate.trim() : null,
          expiry_date: expiryDate,
        };
        const created = await bffFetch<Permit>(
          `/v1/projects/${projectId}/permits`,
          {
            method: "POST",
            body: JSON.stringify(input),
          }
        );
        onSaved(created, false);
      }
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
