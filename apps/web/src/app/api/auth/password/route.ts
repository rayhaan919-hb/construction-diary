import { NextRequest, NextResponse } from "next/server";
import { MUST_CHANGE_COOKIE_NAME } from "@/lib/config";
import { clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";
import { fetchBackendWithAuth } from "@/lib/server-api";

export async function POST(req: NextRequest) {
  let rawBody: string;
  try {
    rawBody = await req.text();
  } catch {
    return NextResponse.json(
      {
        type: "about:blank",
        title: "Invalid request",
        status: 400,
        code: "INVALID_JSON",
        detail: "Invalid request body",
      },
      { status: 400 }
    );
  }

  const outcome = await fetchBackendWithAuth(req, "/v1/me/password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: rawBody,
  });

  if (!outcome.response.ok) {
    const errBody = await outcome.response.text();
    const res = new NextResponse(errBody || null, {
      status: outcome.response.status,
      headers: {
        "Content-Type":
          outcome.response.headers.get("content-type") ??
          "application/problem+json",
      },
    });
    if (outcome.shouldClearCookies) {
      clearAuthCookies(res);
    } else if (outcome.refreshedTokens) {
      setAuthCookies(res, outcome.refreshedTokens);
    }
    return res;
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  if (outcome.refreshedTokens) {
    setAuthCookies(res, outcome.refreshedTokens);
  }
  res.cookies.delete(MUST_CHANGE_COOKIE_NAME);
  return res;
}
