import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  MUST_CHANGE_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
} from "@/lib/config";
import { isJwtExpiredOrExpiring } from "@/lib/jwt";
import {
  buildCookieHeaderWithUpdates,
  clearAuthCookies,
  setAuthCookies,
} from "@/lib/auth-cookies";
import { refreshWithBackend } from "@/lib/auth-refresh";

const PUBLIC_PATHS = new Set(["/login"]);

export async function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;

  const accessToken = req.cookies.get(ACCESS_COOKIE_NAME)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE_NAME)?.value;
  let mustChange = req.cookies.get(MUST_CHANGE_COOKIE_NAME)?.value === "1";

  let refreshedTokens: Awaited<ReturnType<typeof refreshWithBackend>> | null = null;
  let hasValidSession = Boolean(accessToken && !isJwtExpiredOrExpiring(accessToken, 30));

  // Refresh expired/missing access token in middleware so Server Components never need to write cookies.
  if (!hasValidSession && refreshToken) {
    refreshedTokens = await refreshWithBackend(refreshToken);
    if (refreshedTokens.ok) {
      hasValidSession = true;
      mustChange = refreshedTokens.tokens.user.must_change_password;
    } else if (!refreshedTokens.transient) {
      // 401 / invalid refresh token: session is dead
      if (PUBLIC_PATHS.has(pathname)) {
        const res = NextResponse.next();
        clearAuthCookies(res);
        return res;
      }
      const loginUrl = new URL("/login", req.url);
      if (pathname !== "/") {
        loginUrl.searchParams.set("next", `${pathname}${search}`);
      }
      const res = NextResponse.redirect(loginUrl);
      clearAuthCookies(res);
      return res;
    } else if (accessToken) {
      // Transient backend outage while access token still present: allow SSR to render error/retry UI
      hasValidSession = true;
    } else {
      // Transient outage while access token missing but refresh token present: let SSR attempt or show error
      hasValidSession = true;
    }
  }

  const isPublic = PUBLIC_PATHS.has(pathname);

  if (!hasValidSession && !isPublic) {
    const loginUrl = new URL("/login", req.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("next", `${pathname}${search}`);
    }
    return NextResponse.redirect(loginUrl);
  }

  if (hasValidSession && isPublic) {
    const dest = mustChange ? "/change-password" : "/";
    const res = NextResponse.redirect(new URL(dest, req.url));
    if (refreshedTokens?.ok) {
      setAuthCookies(res, refreshedTokens.tokens);
    }
    return res;
  }

  if (hasValidSession && mustChange && pathname !== "/change-password") {
    const res = NextResponse.redirect(new URL("/change-password", req.url));
    if (refreshedTokens?.ok) {
      setAuthCookies(res, refreshedTokens.tokens);
    }
    return res;
  }

  if (refreshedTokens?.ok) {
    const requestHeaders = new Headers(req.headers);
    const updatedCookieHeader = buildCookieHeaderWithUpdates(
      req.cookies.getAll(),
      {
        [ACCESS_COOKIE_NAME]: refreshedTokens.tokens.access_token,
        [REFRESH_COOKIE_NAME]: refreshedTokens.tokens.refresh_token,
        [MUST_CHANGE_COOKIE_NAME]: refreshedTokens.tokens.user.must_change_password
          ? "1"
          : null,
      }
    );
    requestHeaders.set("cookie", updatedCookieHeader);

    const res = NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
    setAuthCookies(res, refreshedTokens.tokens);
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|api/).*)",
  ],
};
