import { describe, expect, it } from "vitest";
import sharp from "sharp";
import type { DailyReport, Permit, Project } from "@/lib/types";
import { renderDailyReportPdfBuffer } from "@/lib/pdf/daily-report-pdf";
import {
  fetchCompressedLogPhotos,
  resolveServerMediaUrl,
} from "@/lib/pdf/photo-fetcher";

describe("PDF daily report generation", () => {
  it("rewrites localhost local media URLs when API_BASE_URL points to internal service", () => {
    const prev = process.env.API_BASE_URL;
    process.env.API_BASE_URL = "http://api:8000";
    try {
      expect(
        resolveServerMediaUrl(
          "http://localhost:8000/v1/media/local/projects%2F1%2Fphotos%2F2.jpg?sig=abc&exp=123"
        )
      ).toBe(
        "http://api:8000/v1/media/local/projects%2F1%2Fphotos%2F2.jpg?sig=abc&exp=123"
      );
      expect(
        resolveServerMediaUrl("https://storage.googleapis.com/bucket/photo.jpg?sig=1")
      ).toBe("https://storage.googleapis.com/bucket/photo.jpg?sig=1");
    } finally {
      process.env.API_BASE_URL = prev;
    }
  });

  it("renders a valid offline PDF buffer with bundled fonts, permits, RTL Urdu transcript, and compressed JPEG photo", async () => {
    const tinyJpeg = await sharp({
      create: {
        width: 16,
        height: 16,
        channels: 3,
        background: { r: 217, g: 119, b: 6 },
      },
    })
      .jpeg()
      .toBuffer();

    const photoUri = `data:image/jpeg;base64,${tinyJpeg.toString("base64")}`;
    const photoMap = new Map<string, string>([
      ["11111111-1111-4111-8111-111111111111", photoUri],
    ]);

    const project: Project = {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      name: "Margalla Commercial Tower",
      site_address: "Plot 14-B, F-8 Markaz, Islamabad",
      owner_phone: "+92 300 1234567",
      timezone: "Asia/Karachi",
      allow_photo_gps: false,
      created_at: "2026-11-01T08:00:00Z",
      updated_at: "2026-11-14T08:00:00Z",
      deleted_at: null,
      server_version: 12,
    };

    const permits: Permit[] = [
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        project_id: project.id,
        permit_name: "CDA Building Plan",
        authority: "CDA",
        permit_number: "CDA-2026-101",
        issue_date: "2026-01-10",
        expiry_date: "2026-11-20",
        status: "EXPIRING_SOON",
        days_to_expiry: 6,
        document_photo_uri: null,
        document_photo_url: null,
        created_by: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        created_at: "2026-01-10T00:00:00Z",
        updated_at: "2026-01-10T00:00:00Z",
        deleted_at: null,
        server_version: 2,
      },
    ];

    const report: DailyReport = {
      project_id: project.id,
      project_name: project.name,
      log_date: "2026-11-14",
      labor_max: 14,
      log_count: 2,
      pending_extraction_count: 1,
      tasks_completed: ["Foundation pouring Block B"],
      material_deliveries: ["40 bags OPC cement"],
      blockers: ["Water pump pressure low on east trench"],
      logs: [
        {
          id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
          project_id: project.id,
          author_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          author_name: "Tariq Mahmood",
          log_date: "2026-11-14",
          recorded_at: "2026-11-14T09:15:00Z",
          notes: "Concrete slump verified on site.",
          audio_uri: "local://projects/a/audio/d.m4a",
          audio_duration_ms: 42000,
          audio_upload_status: "UPLOADED",
          extraction_status: "DONE",
          extraction_attempts: 1,
          extraction_error: null,
          extraction_model: "gemini-2.5-flash",
          extracted_at: "2026-11-14T09:16:00Z",
          transcript: "آج 14 مزدوروں نے بلاک بی کی بنیاد ڈالی۔",
          detected_language: "ur",
          structured_summary: {
            tasks_completed: ["Foundation pouring Block B"],
            labor_count: 14,
            material_deliveries: ["40 bags OPC cement"],
            blockers: ["Water pump pressure low on east trench"],
          },
          edited_by_human: false,
          photos: [
            {
              id: "11111111-1111-4111-8111-111111111111",
              site_log_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
              storage_uri: "local://projects/a/photos/1.jpg",
              upload_status: "UPLOADED",
              url: "http://localhost:8000/v1/media/local/1.jpg",
              width: 16,
              height: 16,
              byte_size: tinyJpeg.byteLength,
              taken_at: "2026-11-14T09:14:00Z",
              sort_order: 0,
              deleted_at: null,
              server_version: 5,
            },
          ],
          client_updated_at: "2026-11-14T09:15:00Z",
          created_at: "2026-11-14T09:15:05Z",
          updated_at: "2026-11-14T09:16:00Z",
          deleted_at: null,
          server_version: 6,
        },
      ],
      permits,
    };

    const pdf = await renderDailyReportPdfBuffer({
      project,
      report,
      permits,
      photoDataUris: photoMap,
      generatedAtIso: "2026-11-14T12:00:00Z",
    });

    expect(pdf.subarray(0, 5).toString("ascii")).toBe("%PDF-");
    expect(pdf.byteLength).toBeGreaterThan(10_000);
  });

  it("gracefully skips unavailable photo URLs without failing", async () => {
    const map = await fetchCompressedLogPhotos([
      {
        id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        project_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        author_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        log_date: "2026-11-14",
        recorded_at: "2026-11-14T09:15:00Z",
        audio_upload_status: "NONE",
        extraction_status: "NOT_STARTED",
        extraction_attempts: 0,
        edited_by_human: false,
        photos: [
          {
            id: "22222222-2222-4222-8222-222222222222",
            site_log_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            storage_uri: "local://missing.jpg",
            upload_status: "UPLOADED",
            url: "http://127.0.0.1:1/unreachable.jpg",
            sort_order: 0,
            server_version: 1,
          },
        ],
        client_updated_at: "2026-11-14T09:15:00Z",
        created_at: "2026-11-14T09:15:00Z",
        updated_at: "2026-11-14T09:15:00Z",
        server_version: 1,
      },
    ]);

    expect(map.size).toBe(0);
  });
});
