import type { NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  DEFAULT_ACCESS_TTL_SECONDS,
  MUST_CHANGE_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  REFRESH_TTL_SECONDS,
  isSessionCookieSecure,
} from "./config";

export interface SessionCookieTokens {
  access_token: string;
  refresh_token: string;
  access_expires_in?: number;
  user?: {
    must_change_password?: boolean;
  };
}

export function setAuthCookies(
  response: NextResponse,
  tokens: SessionCookieTokens
): void {
  const secure = isSessionCookieSecure();
  const accessMaxAge =
    typeof tokens.access_expires_in === "number" && tokens.access_expires_in > 0
      ? tokens.access_expires_in
      : DEFAULT_ACCESS_TTL_SECONDS;

  response.cookies.set(ACCESS_COOKIE_NAME, tokens.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: accessMaxAge,
  });

  response.cookies.set(REFRESH_COOKIE_NAME, tokens.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure,
    path: "/",
    maxAge: REFRESH_TTL_SECONDS,
  });

  if (tokens.user?.must_change_password) {
    response.cookies.set(MUST_CHANGE_COOKIE_NAME, "1", {
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      maxAge: REFRESH_TTL_SECONDS,
    });
  } else {
    response.cookies.delete(MUST_CHANGE_COOKIE_NAME);
  }
}

export function clearAuthCookies(response: NextResponse): void {
  response.cookies.delete(ACCESS_COOKIE_NAME);
  response.cookies.delete(REFRESH_COOKIE_NAME);
  response.cookies.delete(MUST_CHANGE_COOKIE_NAME);
}

/**
 * Rebuilds the Cookie header for NextResponse.next({ request: { headers } })
 * so Server Components invoked in the same request read freshly rotated tokens.
 */
export function buildCookieHeaderWithUpdates(
  existingCookies: ReadonlyArray<{ name: string; value: string }>,
  updates: Record<string, string | null>
): string {
  const map = new Map<string, string>();
  for (const cookie of existingCookies) {
    map.set(cookie.name, cookie.value);
  }
  for (const [name, value] of Object.entries(updates)) {
    if (value === null) {
      map.delete(name);
    } else {
      map.set(name, value);
    }
  }
  return Array.from(map.entries())
    .map(([name, value]) => `${name}=${value}`)
    .join("; ");
}
