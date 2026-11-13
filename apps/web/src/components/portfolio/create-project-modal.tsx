"use client";

import React, { useState } from "react";
import { AlertCircle } from "lucide-react";
import type { Project, ProjectInput } from "@/lib/types";
import { bffFetch } from "@/lib/bff-client";
import { getErrorMessage } from "@/lib/problem";
import { Modal } from "@/components/ui/modal";

const COMMON_TIMEZONES = [
  "Asia/Karachi",
  "Asia/Dubai",
  "Asia/Riyadh",
  "Asia/Kolkata",
  "Europe/London",
  "America/New_York",
  "UTC",
];

export function CreateProjectModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const [name, setName] = useState("");
  const [siteAddress, setSiteAddress] = useState("");
  const [ownerPhone, setOwnerPhone] = useState("");
  const [timezone, setTimezone] = useState("Asia/Karachi");
  const [allowPhotoGps, setAllowPhotoGps] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function resetForm() {
    setName("");
    setSiteAddress("");
    setOwnerPhone("");
    setTimezone("Asia/Karachi");
    setAllowPhotoGps(false);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const payload: ProjectInput = {
      name: name.trim(),
      site_address: siteAddress.trim(),
      owner_phone: ownerPhone.trim() ? ownerPhone.trim() : null,
      timezone: timezone.trim() || "Asia/Karachi",
      allow_photo_gps: allowPhotoGps,
    };

    try {
      const created = await bffFetch<Project>("/v1/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      resetForm();
      onCreated(created);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to create project"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New Construction Project"
      subtitle="Configure site address and local project timezone for daily log grouping."
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
            htmlFor="project-name"
            className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
          >
            Project Name
          </label>
          <input
            id="project-name"
            type="text"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Margalla Commercial Tower"
            className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
          />
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="project-address"
            className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
          >
            Site Address
          </label>
          <textarea
            id="project-address"
            required
            rows={2}
            value={siteAddress}
            onChange={(e) => setSiteAddress(e.target.value)}
            placeholder="Plot 14-B, Sector F-8 Markaz, Islamabad"
            className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label
              htmlFor="project-timezone"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Project Timezone (IANA)
            </label>
            <input
              id="project-timezone"
              list="iana-timezone-presets"
              required
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
            <datalist id="iana-timezone-presets">
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz} />
              ))}
            </datalist>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="owner-phone"
              className="block text-xs font-semibold uppercase tracking-wide text-[#475569]"
            >
              Owner Phone (Optional)
            </label>
            <input
              id="owner-phone"
              type="tel"
              value={ownerPhone}
              onChange={(e) => setOwnerPhone(e.target.value)}
              placeholder="+92 300 1234567"
              className="w-full rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 font-mono text-sm text-[#0F172A] focus:border-[#D97706] focus:outline-none"
            />
          </div>
        </div>

        <label className="flex items-start gap-2.5 rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3 cursor-pointer">
          <input
            type="checkbox"
            checked={allowPhotoGps}
            onChange={(e) => setAllowPhotoGps(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-[#CBD5E1] accent-[#D97706]"
          />
          <span className="text-xs text-[#475569]">
            <strong className="block font-semibold text-[#0F172A]">
              Retain EXIF GPS coordinates on site photos
            </strong>
            Disabled by default for crew privacy; mobile app strips EXIF GPS unless enabled.
          </span>
        </label>

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
            {submitting ? "Creating..." : "Create Project"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
