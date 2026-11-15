import { NextRequest, NextResponse } from "next/server";
import { getApiBaseUrl, isDemoMode } from "@/lib/config";
import { verifySameOriginRequest } from "@/lib/csrf";

export async function POST(req: NextRequest) {
  if (!verifySameOriginRequest(req)) {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Forbidden",
        status: 403,
        code: "CSRF_FORBIDDEN",
        detail: "Cross-origin password reset requests are blocked.",
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
    return NextResponse.json(
      {
        accepted: true,
        message: "If an account exists for that email, reset instructions have been issued.",
        dev_reset_token: "demo-reset-token-123",
      },
      { status: 202 }
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${getApiBaseUrl()}/v1/auth/password-reset/request`, {
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

  const raw = await upstream.text();
  return new NextResponse(raw || null, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("content-type") ?? "application/json",
    },
  });
}
