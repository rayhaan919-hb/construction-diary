import { NextRequest, NextResponse } from "next/server";
import { getApiBaseUrl, isDemoMode } from "@/lib/config";
import { verifySameOriginRequest } from "@/lib/csrf";
import { setAuthCookies } from "@/lib/auth-cookies";
import type { RefreshedTokenPair } from "@/lib/auth-refresh";
import { createDemoTokenPair } from "@/lib/demo-data";

export async function POST(req: NextRequest) {
  if (!verifySameOriginRequest(req)) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Forbidden",
        status: 403,
        code: "CSRF_FORBIDDEN",
        detail: "Cross-origin registration requests are blocked.",
      },
      { status: 403 }
    );
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Invalid request",
        status: 400,
        code: "INVALID_JSON",
        detail: "Request body must be valid JSON",
      },
      { status: 400 }
    );
  }

  if (isDemoMode()) {
    const email =
      body && typeof body === "object" && "owner_email" in body && typeof body.owner_email === "string"
        ? body.owner_email
        : undefined;
    const tokens = createDemoTokenPair(email);
    const res = NextResponse.json({ user: tokens.user }, { status: 201 });
    setAuthCookies(res, tokens);
    return res;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${getApiBaseUrl()}/v1/organizations/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (err) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "API unavailable",
        status: 503,
        code: "BACKEND_UNAVAILABLE",
        detail:
          err instanceof Error
            ? `Could not connect to API server: ${err.message}`
            : "Could not connect to API server",
      },
      { status: 503 }
    );
  }

  if (!upstream.ok) {
    const raw = await upstream.text();
    return new NextResponse(raw || null, {
      status: upstream.status,
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/problem+json",
      },
    });
  }

  const data = (await upstream.json()) as {
    organization: unknown;
    user: unknown;
    tokens: RefreshedTokenPair;
  };
  const res = NextResponse.json(
    { organization: data.organization, user: data.user },
    { status: 201 }
  );
  setAuthCookies(res, data.tokens);
  return res;
}
