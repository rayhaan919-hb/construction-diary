import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import {
  DELETE as bffDelete,
  GET as bffGet,
  PATCH as bffPatch,
  POST as bffPost,
} from "@/app/api/bff/[...path]/route";
import { GET as pdfGet } from "@/app/api/reports/[projectId]/[date]/pdf/route";
import { POST as loginPost } from "@/app/api/auth/login/route";
import { isDemoMode } from "@/lib/config";
import {
  DEMO_PROJECT_ONE_ID,
  DEMO_USER_ID,
  resetDemoStore,
} from "@/lib/demo-data";
import { getTodayInTimezone } from "@/lib/format";
import { serverApiFetch } from "@/lib/server-api";
import type {
  DailyReport,
  Permit,
  Project,
  ProjectSummary,
  TimelineResponse,
} from "@/lib/types";

const mockCookiesGet = vi.fn();

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: mockCookiesGet,
  }),
}));

/**
 * Blocks any external HTTP(S) network fetch while allowing internal data: URLs
 * (such as @react-pdf/renderer's Yoga WASM initialization blob).
 */
function trapExternalFetch(): string[] {
  const realFetch = globalThis.fetch.bind(globalThis);
  const externalUrls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const target =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    if (target.startsWith("data:")) {
      return realFetch(input, init);
    }
    externalUrls.push(target);
    return Promise.reject(new Error(`Unexpected network fetch: ${target}`));
  });
  return externalUrls;
}

describe("Web Demo Mode (NEXT_PUBLIC_DEMO_MODE=true)", () => {
  const prevDemoFlag = process.env.NEXT_PUBLIC_DEMO_MODE;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_DEMO_MODE = "true";
    resetDemoStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mockCookiesGet.mockReset();
    process.env.NEXT_PUBLIC_DEMO_MODE = prevDemoFlag;
  });

  it("toggles cleanly via isDemoMode() and enforces 401 auth when demo mode is off", async () => {
    expect(isDemoMode()).toBe(true);

    process.env.NEXT_PUBLIC_DEMO_MODE = "false";
    expect(isDemoMode()).toBe(false);
    mockCookiesGet.mockReturnValue(undefined);

    await expect(serverApiFetch("/v1/projects")).rejects.toMatchObject({
      status: 401,
      code: "TOKEN_EXPIRED",
    });

    const bffUnauthRes = await bffGet(
      new NextRequest("http://localhost:3000/api/bff/v1/projects"),
      { params: Promise.resolve({ path: ["v1", "projects"] }) }
    );
    expect(bffUnauthRes.status).toBe(401);
    expect(await bffUnauthRes.json()).toMatchObject({
      code: "TOKEN_EXPIRED",
    });
  });

  it("serves realistic bilingual portfolio, permits, weather notes, and photos via serverApiFetch with zero external calls", async () => {
    const externalUrls = trapExternalFetch();

    const portfolio = await serverApiFetch<ProjectSummary[]>("/v1/projects");
    expect(portfolio).toHaveLength(3);
    expect(portfolio.map((p) => p.permit_health).sort()).toEqual([
      "EXPIRED",
      "OK",
      "WARN",
    ]);

    const today = getTodayInTimezone("Asia/Karachi");
    const report = await serverApiFetch<DailyReport>(
      `/v1/projects/${DEMO_PROJECT_ONE_ID}/days/${today}`
    );

    expect(report.log_count).toBeGreaterThanOrEqual(2);
    expect(report.labor_max).toBe(34);
    expect(report.material_deliveries.length).toBeGreaterThan(0);
    expect(report.blockers.length).toBeGreaterThan(0);

    const languages = report.logs.map((l) => l.detected_language);
    expect(languages).toContain("en");
    expect(languages).toContain("ur");

    const notesJoined = report.logs.map((l) => l.notes ?? "").join(" ");
    expect(notesJoined).toContain("Weather:");

    const photos = report.logs.flatMap((l) => l.photos ?? []);
    expect(photos.length).toBeGreaterThanOrEqual(2);
    expect(photos[0]?.url?.startsWith("data:image/jpeg;base64,")).toBe(true);

    const permits = await serverApiFetch<Permit[]>(
      `/v1/projects/${DEMO_PROJECT_ONE_ID}/permits`
    );
    expect(permits.some((p) => p.status === "EXPIRING_SOON")).toBe(true);
    expect(permits.some((p) => p.status === "ACTIVE")).toBe(true);

    expect(externalUrls).toEqual([]);
  });

  it("supports BFF fallback reads, mutations, pagination, extraction retry, and offline login", async () => {
    const externalUrls = trapExternalFetch();

    // BFF GET /api/bff/v1/projects
    const listRes = await bffGet(
      new NextRequest("http://localhost:3000/api/bff/v1/projects"),
      { params: Promise.resolve({ path: ["v1", "projects"] }) }
    );
    expect(listRes.status).toBe(200);
    const listJson = (await listRes.json()) as ProjectSummary[];
    expect(listJson).toHaveLength(3);

    // BFF POST /api/bff/v1/projects
    const createRes = await bffPost(
      new NextRequest("http://localhost:3000/api/bff/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Demo Bridge Overpass",
          site_address: "Zero Point Interchange, Islamabad",
          timezone: "Asia/Karachi",
          allow_photo_gps: true,
        }),
      }),
      { params: Promise.resolve({ path: ["v1", "projects"] }) }
    );
    expect(createRes.status).toBe(201);
    const createdProject = (await createRes.json()) as Project;
    expect(createdProject.name).toBe("Demo Bridge Overpass");

    // BFF PATCH + DELETE /api/bff/v1/permits/[id]
    const permitsRes = await bffGet(
      new NextRequest(
        `http://localhost:3000/api/bff/v1/projects/${DEMO_PROJECT_ONE_ID}/permits`
      ),
      {
        params: Promise.resolve({
          path: ["v1", "projects", DEMO_PROJECT_ONE_ID, "permits"],
        }),
      }
    );
    expect(permitsRes.status).toBe(200);
    const firstPermit = ((await permitsRes.json()) as Permit[])[0]!;

    const patchPermitRes = await bffPatch(
      new NextRequest(
        `http://localhost:3000/api/bff/v1/permits/${firstPermit.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ authority: "CDA Updated" }),
        }
      ),
      { params: Promise.resolve({ path: ["v1", "permits", firstPermit.id] }) }
    );
    expect(patchPermitRes.status).toBe(200);
    expect(((await patchPermitRes.json()) as Permit).authority).toBe(
      "CDA Updated"
    );

    const delPermitRes = await bffDelete(
      new NextRequest(
        `http://localhost:3000/api/bff/v1/permits/${firstPermit.id}`,
        { method: "DELETE" }
      ),
      { params: Promise.resolve({ path: ["v1", "permits", firstPermit.id] }) }
    );
    expect(delPermitRes.status).toBe(204);

    // Timeline pagination (days=7 -> next_before -> page 2)
    const tlPage1Res = await bffGet(
      new NextRequest(
        `http://localhost:3000/api/bff/v1/projects/${DEMO_PROJECT_ONE_ID}/timeline?days=7`
      ),
      {
        params: Promise.resolve({
          path: ["v1", "projects", DEMO_PROJECT_ONE_ID, "timeline"],
        }),
      }
    );
    expect(tlPage1Res.status).toBe(200);
    const tlPage1 = (await tlPage1Res.json()) as TimelineResponse;
    expect(tlPage1.days).toHaveLength(7);
    expect(tlPage1.next_before).not.toBeNull();

    const tlPage2Res = await bffGet(
      new NextRequest(
        `http://localhost:3000/api/bff/v1/projects/${DEMO_PROJECT_ONE_ID}/timeline?before=${tlPage1.next_before}&days=7`
      ),
      {
        params: Promise.resolve({
          path: ["v1", "projects", DEMO_PROJECT_ONE_ID, "timeline"],
        }),
      }
    );
    expect(tlPage2Res.status).toBe(200);
    const tlPage2 = (await tlPage2Res.json()) as TimelineResponse;
    expect(tlPage2.days.length).toBeGreaterThanOrEqual(1);

    // Retry FAILED voice extraction via BFF POST /api/bff/v1/logs/extract
    const retryRes = await bffPost(
      new NextRequest("http://localhost:3000/api/bff/v1/logs/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          log_id: "33333333-3333-4333-8333-333333333106",
        }),
      }),
      { params: Promise.resolve({ path: ["v1", "logs", "extract"] }) }
    );
    expect(retryRes.status).toBe(202);
    expect(await retryRes.json()).toMatchObject({
      extraction_status: "DONE",
    });

    // Demo login route sets cookies offline
    const loginRes = await loginPost(
      new NextRequest("http://localhost:3000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "buyer@demo.example", password: "demo" }),
      })
    );
    expect(loginRes.status).toBe(200);
    const loginJson = (await loginRes.json()) as {
      user: { id: string; email: string };
    };
    expect(loginJson.user.id).toBe(DEMO_USER_ID);
    expect(loginJson.user.email).toBe("buyer@demo.example");

    expect(externalUrls).toEqual([]);
  });

  it("exports a valid PDF daily report with bilingual transcript and demo JPEG photos offline", async () => {
    const externalUrls = trapExternalFetch();

    const today = getTodayInTimezone("Asia/Karachi");
    const pdfRes = await pdfGet(
      new NextRequest(
        `http://localhost:3000/api/reports/${DEMO_PROJECT_ONE_ID}/${today}/pdf`
      ),
      {
        params: Promise.resolve({
          projectId: DEMO_PROJECT_ONE_ID,
          date: today,
        }),
      }
    );

    expect(pdfRes.status).toBe(200);
    expect(pdfRes.headers.get("Content-Type")).toBe("application/pdf");
    expect(pdfRes.headers.get("Content-Disposition")).toContain(".pdf");

    const bytes = Buffer.from(await pdfRes.arrayBuffer());
    expect(bytes.subarray(0, 5).toString("ascii")).toBe("%PDF-");
    expect(bytes.byteLength).toBeGreaterThan(25000);
    expect(externalUrls).toEqual([]);
  });
});
