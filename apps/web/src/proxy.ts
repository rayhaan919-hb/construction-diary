import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  MUST_CHANGE_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  getEdgeJwtSecret,
  isDemoMode,
} from "@/lib/config";
import { buildContentSecurityPolicy } from "@/lib/csp";
import {
  isJwtExpiredOrExpiring,
  verifyJwtHs256Signature,
} from "@/lib/jwt";
import {
  buildCookieHeaderWithUpdates,
  clearAuthCookies,
  setAuthCookies,
} from "@/lib/auth-cookies";
import { refreshWithBackend } from "@/lib/auth-refresh";

const PUBLIC_PATHS = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/invite",
]);

function withCspHeader(res: NextResponse): NextResponse {
  res.headers.set(
    "Content-Security-Policy",
    buildContentSecurityPolicy([
      process.env.API_BASE_URL,
      process.env.PUBLIC_API_BASE_URL,
      process.env.INTERNAL_API_BASE_URL,
    ])
  );
  return res;
}

function applyNextWithUpdatedCookies(
  req: NextRequest,
  tokens: NonNullable<
    Extract<Awaited<ReturnType<typeof refreshWithBackend>>, { ok: true }>["tokens"]
  >
): NextResponse {
  const requestHeaders = new Headers(req.headers);
  const updatedCookieHeader = buildCookieHeaderWithUpdates(req.cookies.getAll(), {
    [ACCESS_COOKIE_NAME]: tokens.access_token,
    [REFRESH_COOKIE_NAME]: tokens.refresh_token,
    [MUST_CHANGE_COOKIE_NAME]: tokens.user.must_change_password ? "1" : null,
  });
  requestHeaders.set("cookie", updatedCookieHeader);

  const res = NextResponse.next({
    request: { headers: requestHeaders },
  });
  setAuthCookies(res, tokens);
  return res;
}

export async function proxy(req: NextRequest) {
  return withCspHeader(await handleProxy(req));
}

async function handleProxy(req: NextRequest): Promise<NextResponse> {
  if (isDemoMode()) {
    return NextResponse.next();
  }

  const { pathname, search } = req.nextUrl;
  const isPublic = PUBLIC_PATHS.has(pathname);

  const accessToken = req.cookies.get(ACCESS_COOKIE_NAME)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE_NAME)?.value;
  let mustChange = req.cookies.get(MUST_CHANGE_COOKIE_NAME)?.value === "1";

  let refreshedTokens: Awaited<ReturnType<typeof refreshWithBackend>> | null = null;
  let hasValidSession = Boolean(
    accessToken && !isJwtExpiredOrExpiring(accessToken, 30)
  );

  // If a signing secret is configured on the web server, verify HS256 signature cryptographically.
  const jwtSecret = getEdgeJwtSecret();
  if (hasValidSession && accessToken && jwtSecret) {
    const signatureOk = await verifyJwtHs256Signature(accessToken, jwtSecret);
    if (!signatureOk) {
      hasValidSession = false;
    }
  }

  let transientOutage = false;

  // Refresh expired/missing/unverified access token in middleware so Server Components stay read-only.
  if (!hasValidSession && refreshToken) {
    refreshedTokens = await refreshWithBackend(refreshToken);
    if (refreshedTokens.ok) {
      hasValidSession = true;
      mustChange = refreshedTokens.tokens.user.must_change_password;
    } else if (!refreshedTokens.transient) {
      if (isPublic) {
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
    } else {
      // Transient backend outage: allow page render with 503 Retry UI if either cookie exists
      transientOutage = true;
      hasValidSession = Boolean(accessToken || refreshToken);
    }
  }

  if (!hasValidSession && !isPublic) {
    const loginUrl = new URL("/login", req.url);
    if (pathname !== "/") {
      loginUrl.searchParams.set("next", `${pathname}${search}`);
    }
    return NextResponse.redirect(loginUrl);
  }

  if (hasValidSession && !transientOutage && isPublic && pathname !== "/invite") {
    const dest = mustChange ? "/change-password" : "/";
    const res = NextResponse.redirect(new URL(dest, req.url));
    if (refreshedTokens?.ok) {
      setAuthCookies(res, refreshedTokens.tokens);
    }
    return res;
  }

  if (
    hasValidSession &&
    !transientOutage &&
    mustChange &&
    pathname !== "/change-password"
  ) {
    const res = NextResponse.redirect(new URL("/change-password", req.url));
    if (refreshedTokens?.ok) {
      setAuthCookies(res, refreshedTokens.tokens);
    }
    return res;
  }

  if (refreshedTokens?.ok) {
    return applyNextWithUpdatedCookies(req, refreshedTokens.tokens);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg|api/).*)"],
};
