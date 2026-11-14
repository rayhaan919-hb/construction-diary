import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST as loginPost } from "@/app/api/auth/login/route";
import { POST as logoutPost } from "@/app/api/auth/logout/route";
import { POST as passwordPost } from "@/app/api/auth/password/route";
import { GET as healthGet } from "@/app/api/health/route";
import {
  ACCESS_COOKIE_NAME,
  MUST_CHANGE_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
} from "@/lib/config";

function makeJwt(expOffsetSeconds = 900): string {
  const exp = Math.floor(Date.now() / 1000) + expOffsetSeconds;
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify({ sub: "user-1", exp })).toString("base64url");
  return `${header}.${payload}.sig`;
}

describe("Web auth & health route handlers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 200 ok from /api/health", async () => {
    const res = await healthGet();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
  });

  it("rejects malformed JSON on /api/auth/login with 400 INVALID_JSON", async () => {
    const req = new NextRequest("http://localhost:3000/api/auth/login", {
      method: "POST",
      body: "{bad json",
      headers: { "Content-Type": "application/json" },
    });

    const res = await loginPost(req);
    expect(res.status).toBe(400);
    expect((await res.json()).code).toBe("INVALID_JSON");
  });

  it("maps network failure on /api/auth/login to 503 BACKEND_UNAVAILABLE", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));
    const req = new NextRequest("http://localhost:3000/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "owner@example.com", password: "secret" }),
      headers: { "Content-Type": "application/json" },
    });

    const res = await loginPost(req);
    expect(res.status).toBe(503);
    expect((await res.json()).code).toBe("BACKEND_UNAVAILABLE");
  });

  it("passes upstream 401 problem+json and avoids setting cookies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Unauthorized",
          status: 401,
          code: "INVALID_CREDENTIALS",
          detail: "Incorrect email or password",
        }),
        { status: 401, headers: { "Content-Type": "application/problem+json" } }
      )
    );

    const req = new NextRequest("http://localhost:3000/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "owner@example.com", password: "wrong" }),
      headers: { "Content-Type": "application/json" },
    });

    const res = await loginPost(req);
    expect(res.status).toBe(401);
    expect((await res.json()).code).toBe("INVALID_CREDENTIALS");
    expect(res.cookies.get(ACCESS_COOKIE_NAME)?.value).toBeUndefined();
    expect(res.cookies.get(REFRESH_COOKIE_NAME)?.value).toBeUndefined();
  });

  it("sets httpOnly cookies and sd_must_change on invited login and adds device_label=web", async () => {
    const access = makeJwt(900);
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: access,
          refresh_token: "refresh_1",
          access_expires_in: 900,
          refresh_expires_at: "2027-01-13T00:00:00Z",
          user: {
            id: "00000000-0000-4000-8000-000000000001",
            email: "newsup@example.com",
            full_name: "New Sup",
            role: "SUPERVISOR",
            preferred_locale: "en",
            must_change_password: true,
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    const req = new NextRequest("http://localhost:3000/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: "newsup@example.com", password: "temppw123" }),
      headers: { "Content-Type": "application/json" },
    });

    const res = await loginPost(req);
    expect(res.status).toBe(200);
    const sentBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(sentBody.device_label).toBe("web");

    const accessCookie = res.cookies.get(ACCESS_COOKIE_NAME);
    const refreshCookie = res.cookies.get(REFRESH_COOKIE_NAME);
    expect(accessCookie?.value).toBe(access);
    expect(accessCookie?.httpOnly).toBe(true);
    expect(refreshCookie?.value).toBe("refresh_1");
    expect(res.cookies.get(MUST_CHANGE_COOKIE_NAME)?.value).toBe("1");
  });

  it("clears sd_must_change cookie on successful /api/auth/password change", async () => {
    const validAccess = makeJwt(600);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));

    const req = new NextRequest("http://localhost:3000/api/auth/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: "temppw123",
        new_password: "newStrongPassword99",
      }),
      headers: {
        "Content-Type": "application/json",
        cookie: `${ACCESS_COOKIE_NAME}=${validAccess}; ${REFRESH_COOKIE_NAME}=ref_1; ${MUST_CHANGE_COOKIE_NAME}=1`,
      },
    });

    const res = await passwordPost(req);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(res.cookies.get(MUST_CHANGE_COOKIE_NAME)?.value ?? "").toBe("");
  });

  it("forwards error payload on failed /api/auth/password and clears cookies when refresh is rejected", async () => {
    const expiredAccess = makeJwt(-60);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Token expired",
          status: 401,
          code: "TOKEN_EXPIRED",
          detail: "Refresh rejected",
        }),
        { status: 401, headers: { "Content-Type": "application/problem+json" } }
      )
    );

    const req = new NextRequest("http://localhost:3000/api/auth/password", {
      method: "POST",
      body: JSON.stringify({ current_password: "a", new_password: "b" }),
      headers: {
        "Content-Type": "application/json",
        cookie: `${ACCESS_COOKIE_NAME}=${expiredAccess}; ${REFRESH_COOKIE_NAME}=stale_ref`,
      },
    });

    const res = await passwordPost(req);
    expect(res.status).toBe(401);
    expect(res.cookies.get(ACCESS_COOKIE_NAME)?.value ?? "").toBe("");
    expect(res.cookies.get(REFRESH_COOKIE_NAME)?.value ?? "").toBe("");
  });

  it("clears all auth cookies on /api/auth/logout even if backend revocation fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("timeout"));
    const req = new NextRequest("http://localhost:3000/api/auth/logout", {
      method: "POST",
      headers: {
        cookie: `${ACCESS_COOKIE_NAME}=tok; ${REFRESH_COOKIE_NAME}=ref; ${MUST_CHANGE_COOKIE_NAME}=1`,
      },
    });

    const res = await logoutPost(req);
    expect(res.status).toBe(200);
    expect(res.cookies.get(ACCESS_COOKIE_NAME)?.value ?? "").toBe("");
    expect(res.cookies.get(REFRESH_COOKIE_NAME)?.value ?? "").toBe("");
    expect(res.cookies.get(MUST_CHANGE_COOKIE_NAME)?.value ?? "").toBe("");
  });
});
