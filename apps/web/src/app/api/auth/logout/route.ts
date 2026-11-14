import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  getApiBaseUrl,
  isDemoMode,
} from "@/lib/config";
import { clearAuthCookies } from "@/lib/auth-cookies";

export async function POST(req: NextRequest) {
  const accessToken = req.cookies.get(ACCESS_COOKIE_NAME)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE_NAME)?.value;

  if (!isDemoMode() && refreshToken) {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
      }
      await fetch(`${getApiBaseUrl()}/v1/auth/logout`, {
        method: "POST",
        headers,
        body: JSON.stringify({ refresh_token: refreshToken }),
        cache: "no-store",
      });
    } catch {
      // Best-effort revocation; cookies are cleared unconditionally
    }
  }

  const res = NextResponse.json({ ok: true }, { status: 200 });
  clearAuthCookies(res);
  return res;
}
