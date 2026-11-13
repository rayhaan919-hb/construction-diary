"use client";

import React from "react";
import { Modal } from "./modal";

export interface LightboxImage {
  url: string;
  title: string;
  meta?: string;
}

export function PhotoLightbox({
  image,
  onClose,
}: {
  image: LightboxImage | null;
  onClose: () => void;
}) {
  return (
    <Modal
      open={Boolean(image)}
      onClose={onClose}
      title={image?.title ?? "Photo"}
      subtitle={image?.meta}
      maxWidthClass="max-w-3xl"
    >
      {image && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-md border border-[#E2E8F0] bg-[#F8FAFC]">
            <img
              src={image.url}
              alt={image.title}
              className="mx-auto max-h-[70vh] w-auto object-contain"
            />
          </div>
          <div className="flex justify-end">
            <a
              href={image.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center rounded-md border border-[#E2E8F0] bg-[#FFFFFF] px-3 py-2 text-sm font-medium text-[#0F172A] hover:bg-[#F8FAFC]"
            >
              Open original in new tab
            </a>
          </div>
        </div>
      )}
    </Modal>
  );
}
