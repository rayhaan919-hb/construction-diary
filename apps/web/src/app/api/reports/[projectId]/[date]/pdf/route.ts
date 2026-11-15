import { NextRequest, NextResponse } from "next/server";
import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { fetchBackendWithAuth } from "@/lib/server-api";
import { fetchCompressedLogPhotos } from "@/lib/pdf/photo-fetcher";
import { renderDailyReportPdfBuffer } from "@/lib/pdf/daily-report-pdf";
import type { DailyReport, Permit, Project } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function isValidCalendarDate(dateStr: string): boolean {
  const m = DATE_RE.exec(dateStr);
  if (!m) return false;
  const year = Number(m[1]);
  const month = Number(m[2]);
  const day = Number(m[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return false;
  const dt = new Date(Date.UTC(year, month - 1, day));
  return (
    dt.getUTCFullYear() === year &&
    dt.getUTCMonth() === month - 1 &&
    dt.getUTCDate() === day
  );
}

function slugifyFilename(input: string): string {
  return (
    input
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48) || "project"
  );
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ projectId: string; date: string }> }
) {
  const { projectId, date } = await context.params;

  if (!UUID_RE.test(projectId) || !isValidCalendarDate(date)) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Invalid report parameters",
        status: 400,
        code: "VALIDATION",
        detail: "projectId must be a UUID and date must be a valid YYYY-MM-DD calendar date",
      },
      { status: 400 }
    );
  }

  const projectOutcome = await fetchBackendWithAuth(
    req,
    `/v1/projects/${projectId}`
  );
  if (!projectOutcome.response.ok) {
    const errText = await projectOutcome.response.text();
    const res = new NextResponse(errText || null, {
      status: projectOutcome.response.status,
      headers: {
        "Content-Type":
          projectOutcome.response.headers.get("content-type") ??
          "application/problem+json",
      },
    });
    if (projectOutcome.shouldClearCookies) {
      clearAuthCookies(res);
    } else if (projectOutcome.refreshedTokens) {
      setAuthCookies(res, projectOutcome.refreshedTokens);
    }
    return res;
  }

  const project = (await projectOutcome.response.json()) as Project;

  const tokenAfterProject = projectOutcome.refreshedTokens?.access_token;
  const reportOutcome = await fetchBackendWithAuth(
    req,
    `/v1/projects/${projectId}/days/${date}`,
    {},
    tokenAfterProject
  );
  let latestTokens =
    reportOutcome.refreshedTokens ?? projectOutcome.refreshedTokens;

  if (!reportOutcome.response.ok) {
    const errText = await reportOutcome.response.text();
    const res = new NextResponse(errText || null, {
      status: reportOutcome.response.status,
      headers: {
        "Content-Type":
          reportOutcome.response.headers.get("content-type") ??
          "application/problem+json",
      },
    });
    if (reportOutcome.shouldClearCookies) {
      clearAuthCookies(res);
    } else if (latestTokens) {
      setAuthCookies(res, latestTokens);
    }
    return res;
  }

  const report = (await reportOutcome.response.json()) as DailyReport;

  let permits: Permit[] = report.permits ?? [];
  if (!report.permits) {
    const permitsOutcome = await fetchBackendWithAuth(
      req,
      `/v1/projects/${projectId}/permits`,
      {},
      latestTokens?.access_token
    );
    latestTokens = permitsOutcome.refreshedTokens ?? latestTokens;
    if (permitsOutcome.response.ok) {
      permits = (await permitsOutcome.response.json()) as Permit[];
    }
  }

  const photoDataUris = await fetchCompressedLogPhotos(report.logs);
  const pdfBuffer = await renderDailyReportPdfBuffer({
    project,
    report,
    permits,
    photoDataUris,
    generatedAtIso: new Date().toISOString(),
  });

  const filename = `site-diary-${slugifyFilename(project.name)}-${date}.pdf`;
  const res = new NextResponse(new Uint8Array(pdfBuffer), {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });

  if (latestTokens) {
    setAuthCookies(res, latestTokens);
  }
  return res;
}
