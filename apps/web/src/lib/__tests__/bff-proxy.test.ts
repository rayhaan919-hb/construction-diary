import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET as bffGet, POST as bffPost } from "@/app/api/bff/[...path]/route";
import { GET as pdfGet } from "@/app/api/reports/[projectId]/[date]/pdf/route";
import {
  ACCESS_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
} from "@/lib/config";
import { ApiError, getErrorMessage, parseErrorResponse } from "@/lib/problem";
import { serverApiFetch } from "@/lib/server-api";

const mockCookiesGet = vi.fn();
const mockRedirect = vi.fn((dest: string) => {
  const err = new Error(`NEXT_REDIRECT:${dest}`);
  throw err;
});

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: mockCookiesGet,
  }),
}));

vi.mock("next/navigation", () => ({
  redirect: (dest: string) => mockRedirect(dest),
}));

function makeJwt(expOffsetSeconds = 900): string {
  const exp = Math.floor(Date.now() / 1000) + expOffsetSeconds;
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({ sub: "user-1", exp })).toString("base64url");
  return `${header}.${payload}.sig`;
}

describe("Problem+JSON error mapping & serverApiFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    mockCookiesGet.mockReset();
    mockRedirect.mockClear();
  });

  it("formats Problem payloads with field errors, text fallbacks, and empty bodies", async () => {
    const fieldErr = await parseErrorResponse(
      new Response(
        JSON.stringify({
          status: 422,
          code: "VALIDATION",
          title: "Validation failed",
          errors: [{ field: "expiry_date", message: "Invalid date" }],
        }),
        { status: 422 }
      )
    );
    expect(fieldErr).toBeInstanceOf(ApiError);
    expect(fieldErr.code).toBe("VALIDATION");
    expect(getErrorMessage(fieldErr)).toBe("expiry_date: Invalid date");

    const plainErr = await parseErrorResponse(
      new Response("upstream crash", { status: 502, statusText: "Bad Gateway" })
    );
    expect(plainErr.code).toBe("HTTP_ERROR");
    expect(plainErr.message).toBe("Bad Gateway");

    const emptyErr = await parseErrorResponse(
      new Response("", { status: 500, statusText: "Internal Error" })
    );
    expect(emptyErr.status).toBe(500);
    expect(emptyErr.message).toBe("Internal Error");
  });

  it("throws 401 when no cookies are present and 503 when only refresh cookie exists", async () => {
    mockCookiesGet.mockReturnValue(undefined);
    await expect(serverApiFetch("/v1/me")).rejects.toMatchObject({
      status: 401,
      code: "TOKEN_EXPIRED",
    });

    mockCookiesGet.mockImplementation((name: string) =>
      name === REFRESH_COOKIE_NAME ? { name, value: "ref_only" } : undefined
    );
    await expect(serverApiFetch("/v1/me")).rejects.toMatchObject({
      status: 503,
      code: "BACKEND_UNAVAILABLE",
    });
  });

  it("returns undefined on HTTP 204 and maps network exceptions to 503", async () => {
    const token = makeJwt(600);
    mockCookiesGet.mockImplementation((name: string) =>
      name === ACCESS_COOKIE_NAME ? { name, value: token } : undefined
    );
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    const result = await serverApiFetch<void>("/v1/projects/123", { method: "DELETE" });
    expect(result).toBeUndefined();

    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("connect ETIMEDOUT"));
    await expect(serverApiFetch("/v1/projects")).rejects.toMatchObject({
      status: 503,
      code: "BACKEND_UNAVAILABLE",
    });
  });
});

describe("BFF proxy error mapping, query forwarding & PDF route validation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    mockCookiesGet.mockReset();
    mockRedirect.mockClear();
  });

  it("rejects invalid proxy paths with 400 INVALID_PATH and missing auth with 401", async () => {
    const badReq = new NextRequest("http://localhost:3000/api/bff/admin/secret");
    const badRes = await bffGet(badReq, {
      params: Promise.resolve({ path: ["admin", "secret"] }),
    });
    expect(badRes.status).toBe(400);
    expect((await badRes.json()).code).toBe("INVALID_PATH");

    const noAuthReq = new NextRequest("http://localhost:3000/api/bff/v1/projects");
    const noAuthRes = await bffGet(noAuthReq, {
      params: Promise.resolve({ path: ["v1", "projects"] }),
    });
    expect(noAuthRes.status).toBe(401);
    expect((await noAuthRes.json()).code).toBe("TOKEN_EXPIRED");
  });

  it("forwards query params, request body, and preserves upstream 403 Problem payloads", async () => {
    const token = makeJwt(600);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Forbidden",
          status: 403,
          code: "FORBIDDEN",
          detail: "Only owners can invite members",
        }),
        { status: 403, headers: { "Content-Type": "application/problem+json" } }
      )
    );

    const req = new NextRequest(
      "http://localhost:3000/api/bff/v1/projects/abc/members?dryRun=true",
      {
        method: "POST",
        body: JSON.stringify({ email: "sup@example.com", full_name: "Sup" }),
        headers: {
          "Content-Type": "application/json",
          cookie: `${ACCESS_COOKIE_NAME}=${token}; ${REFRESH_COOKIE_NAME}=ref_1`,
        },
      }
    );

    const res = await bffPost(req, {
      params: Promise.resolve({ path: ["v1", "projects", "abc", "members"] }),
    });

    expect(res.status).toBe(403);
    expect((await res.json()).code).toBe("FORBIDDEN");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/v1/projects/abc/members?dryRun=true"
    );
  });

  it("transparently rotates expiring access tokens and updates cookies on response", async () => {
    const expiringToken = makeJwt(5);
    const freshToken = makeJwt(900);

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      if (String(url).endsWith("/v1/auth/refresh")) {
        return new Response(
          JSON.stringify({
            access_token: freshToken,
            refresh_token: "rotated_refresh_2",
            access_expires_in: 900,
            refresh_expires_at: "2027-01-13T00:00:00Z",
            user: {
              id: "user-1",
              email: "owner@example.com",
              full_name: "Owner",
              role: "OWNER",
              preferred_locale: "en",
              must_change_password: false,
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify([{ id: "proj-1" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const req = new NextRequest("http://localhost:3000/api/bff/v1/projects", {
      method: "GET",
      headers: {
        cookie: `${ACCESS_COOKIE_NAME}=${expiringToken}; ${REFRESH_COOKIE_NAME}=ref_for_proxy_rotation`,
      },
    });

    const res = await bffGet(req, {
      params: Promise.resolve({ path: ["v1", "projects"] }),
    });

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual([{ id: "proj-1" }]);
    expect(res.cookies.get(ACCESS_COOKIE_NAME)?.value).toBe(freshToken);
    expect(res.cookies.get(REFRESH_COOKIE_NAME)?.value).toBe("rotated_refresh_2");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("validates PDF route parameters before hitting backend", async () => {
    const badReq = new NextRequest(
      "http://localhost:3000/api/reports/not-a-uuid/2026-11-14/pdf"
    );
    const badRes = await pdfGet(badReq, {
      params: Promise.resolve({ projectId: "not-a-uuid", date: "2026-11-14" }),
    });
    expect(badRes.status).toBe(400);
    expect((await badRes.json()).code).toBe("VALIDATION");
  });
});

describe("Portfolio & Project page data loading guards", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    mockCookiesGet.mockReset();
    mockRedirect.mockClear();
  });

  it("redirects unauthenticated users from HomePage and enforces must_change_password", async () => {
    const { default: HomePage } = await import("@/app/page");

    mockCookiesGet.mockReturnValue(undefined);
    await expect(HomePage()).rejects.toThrow("NEXT_REDIRECT:/login");

    const token = makeJwt(600);
    mockCookiesGet.mockImplementation((name: string) =>
      name === ACCESS_COOKIE_NAME ? { name, value: token } : undefined
    );
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      if (String(url).endsWith("/v1/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "new@example.com",
            full_name: "New Sup",
            role: "SUPERVISOR",
            preferred_locale: "en",
            must_change_password: true,
          }),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify([]), { status: 200 });
    });

    await expect(HomePage()).rejects.toThrow("NEXT_REDIRECT:/change-password");
  });

  it("keeps healthy Bento tiles when one ProjectDetailPage sub-request fails", async () => {
    const { default: ProjectDetailPage } = await import(
      "@/app/projects/[id]/page"
    );
    const pid = "11111111-1111-4111-8111-111111111111";
    const token = makeJwt(600);
    mockCookiesGet.mockImplementation((name: string) =>
      name === ACCESS_COOKIE_NAME ? { name, value: token } : undefined
    );

    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      const s = String(url);
      if (s.endsWith("/v1/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "owner@example.com",
            full_name: "Owner",
            role: "OWNER",
            preferred_locale: "en",
            must_change_password: false,
          }),
          { status: 200 }
        );
      }
      if (s.endsWith(`/v1/projects/${pid}`)) {
        return new Response(
          JSON.stringify({
            id: pid,
            name: "Clifton Tower",
            site_address: "Plot 1",
            owner_phone: null,
            timezone: "Asia/Karachi",
            allow_photo_gps: false,
            created_at: "2026-11-01T00:00:00Z",
            updated_at: "2026-11-01T00:00:00Z",
            deleted_at: null,
            server_version: 1,
          }),
          { status: 200 }
        );
      }
      if (s.endsWith(`/v1/projects/${pid}/permits`)) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (s.includes(`/v1/projects/${pid}/timeline`)) {
        return new Response(
          JSON.stringify({
            status: 500,
            code: "INTERNAL_ERROR",
            title: "Timeline down",
            detail: "Timeline temporarily unavailable",
          }),
          { status: 500 }
        );
      }
      return new Response(
        JSON.stringify({
          project_id: pid,
          project_name: "Clifton Tower",
          log_date: "2026-11-14",
          labor_max: 0,
          log_count: 0,
          pending_extraction_count: 0,
          tasks_completed: [],
          material_deliveries: [],
          blockers: [],
          logs: [],
        }),
        { status: 200 }
      );
    });

    const element = await ProjectDetailPage({
      params: Promise.resolve({ id: pid }),
    });
    expect(element.props.initialProject?.name).toBe("Clifton Tower");
    expect(element.props.initialPermits).toEqual([]);
    expect(element.props.initialPermitsError).toBeNull();
    expect(element.props.initialTimeline).toBeNull();
    expect(element.props.initialTimelineError).toBe(
      "Timeline temporarily unavailable"
    );
  });

  it("enforces BFF CSRF protection, encoded path sanitization, 1 MB limit, calendar date checks, and HS256 JWT signatures", async () => {
    const csrfRes = await bffPost(
      new NextRequest("http://localhost:3000/api/bff/v1/projects", {
        method: "POST",
        body: JSON.stringify({ name: "X" }),
        headers: {
          "Content-Type": "application/json",
          "Sec-Fetch-Site": "cross-site",
          cookie: `${ACCESS_COOKIE_NAME}=${makeJwt(600)}`,
        },
      }),
      { params: Promise.resolve({ path: ["v1", "projects"] }) }
    );
    expect(csrfRes.status).toBe(403);
    expect((await csrfRes.json()).code).toBe("CSRF_FORBIDDEN");

    const encodedRes = await bffGet(
      new NextRequest("http://localhost:3000/api/bff/v1/projects/..%2Fadmin"),
      { params: Promise.resolve({ path: ["v1", "projects", "..%2Fadmin"] }) }
    );
    expect(encodedRes.status).toBe(400);
    expect((await encodedRes.json()).code).toBe("INVALID_PATH");

    const bigRes = await bffPost(
      new NextRequest("http://localhost:3000/api/bff/v1/projects", {
        method: "POST",
        body: "{}",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": String(2 * 1024 * 1024),
        },
      }),
      { params: Promise.resolve({ path: ["v1", "projects"] }) }
    );
    expect(bigRes.status).toBe(413);
    expect((await bigRes.json()).code).toBe("PAYLOAD_TOO_LARGE");

    const { GET: pdfGet } = await import("@/app/api/reports/[projectId]/[date]/pdf/route");
    const badDateRes = await pdfGet(
      new NextRequest("http://localhost:3000/api/reports/11111111-1111-4111-8111-111111111111/2026-02-31/pdf"),
      {
        params: Promise.resolve({
          projectId: "11111111-1111-4111-8111-111111111111",
          date: "2026-02-31",
        }),
      }
    );
    expect(badDateRes.status).toBe(400);
    expect((await badDateRes.json()).code).toBe("VALIDATION");

    const { verifyJwtHs256Signature } = await import("@/lib/jwt");
    const crypto = await import("node:crypto");
    const secret = "test-secret-0123456789abcdef0123456789abcdef";
    const hdr = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
    const pld = Buffer.from(
      JSON.stringify({ sub: "u1", exp: Math.floor(Date.now() / 1000) + 600 })
    ).toString("base64url");
    const sig = crypto.createHmac("sha256", secret).update(`${hdr}.${pld}`).digest("base64url");
    expect(await verifyJwtHs256Signature(`${hdr}.${pld}.${sig}`, secret)).toBe(true);
    expect(await verifyJwtHs256Signature(`${hdr}.${pld}.tampered`, secret)).toBe(false);
  });
});
