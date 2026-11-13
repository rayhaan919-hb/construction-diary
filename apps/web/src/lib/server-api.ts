import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  getApiBaseUrl,
} from "./config";
import { isJwtExpiredOrExpiring } from "./jwt";
import { ApiError, parseErrorResponse } from "./problem";
import {
  type RefreshResult,
  type RefreshedTokenPair,
  refreshWithBackend,
} from "./auth-refresh";

interface CachedRefreshEntry {
  promise: Promise<RefreshResult>;
  settledAt?: number;
}

const GRACE_TTL_MS = 5000;
const refreshFlightMap = new Map<string, CachedRefreshEntry>();

/**
 * Single-flight refresh deduplication for Node Route Handlers.
 * Prevents concurrent BFF requests from double-spending a rotated refresh token
 * and triggering TOKEN_REUSED chain revocation.
 */
export async function refreshSessionSingleFlight(
  refreshToken: string
): Promise<RefreshResult> {
  const now = Date.now();
  const existing = refreshFlightMap.get(refreshToken);
  if (existing) {
    if (existing.settledAt === undefined || now - existing.settledAt < GRACE_TTL_MS) {
      return existing.promise;
    }
    refreshFlightMap.delete(refreshToken);
  }

  const entry: CachedRefreshEntry = {
    promise: refreshWithBackend(refreshToken).then((res) => {
      entry.settledAt = Date.now();
      setTimeout(() => {
        const current = refreshFlightMap.get(refreshToken);
        if (current === entry) {
          refreshFlightMap.delete(refreshToken);
        }
      }, GRACE_TTL_MS);
      return res;
    }),
  };

  refreshFlightMap.set(refreshToken, entry);
  return entry.promise;
}

/**
 * Read-only backend fetch for Server Components.
 * Token refresh has already been handled by middleware.ts prior to render.
 */
export async function serverApiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(ACCESS_COOKIE_NAME)?.value;
  const hasRefreshToken = Boolean(cookieStore.get(REFRESH_COOKIE_NAME)?.value);

  if (!accessToken) {
    if (hasRefreshToken) {
      throw new ApiError({
        status: 503,
        code: "BACKEND_UNAVAILABLE",
        title: "API unavailable",
        detail: "Unable to refresh session because the API server is unreachable.",
      });
    }
    throw new ApiError({
      status: 401,
      code: "TOKEN_EXPIRED",
      title: "Unauthorized",
      detail: "Missing access token",
    });
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError({
      status: 503,
      code: "BACKEND_UNAVAILABLE",
      title: "API unavailable",
      detail:
        err instanceof Error
          ? `Could not connect to API server: ${err.message}`
          : "Could not connect to API server",
    });
  }

  if (!res.ok) {
    throw await parseErrorResponse(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export interface BackendAuthFetchOutcome {
  response: Response;
  refreshedTokens: RefreshedTokenPair | null;
  shouldClearCookies: boolean;
}

/**
 * Route-Handler fetch helper supporting proactive + 401-triggered single-flight refresh.
 */
export async function fetchBackendWithAuth(
  req: NextRequest,
  backendPathWithQuery: string,
  init: RequestInit = {},
  tokenOverride?: string
): Promise<BackendAuthFetchOutcome> {
  let accessToken = tokenOverride ?? req.cookies.get(ACCESS_COOKIE_NAME)?.value;
  const refreshToken = req.cookies.get(REFRESH_COOKIE_NAME)?.value;
  let refreshedTokens: RefreshedTokenPair | null = null;

  if (!accessToken && !refreshToken) {
    return {
      response: new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Unauthorized",
          status: 401,
          code: "TOKEN_EXPIRED",
          detail: "Authentication required",
        }),
        {
          status: 401,
          headers: { "Content-Type": "application/problem+json" },
        }
      ),
      refreshedTokens: null,
      shouldClearCookies: false,
    };
  }

  let attemptedRefresh = Boolean(tokenOverride);
  if ((!accessToken || isJwtExpiredOrExpiring(accessToken, 15)) && refreshToken && !tokenOverride) {
    attemptedRefresh = true;
    const refreshRes = await refreshSessionSingleFlight(refreshToken);
    if (refreshRes.ok) {
      refreshedTokens = refreshRes.tokens;
      accessToken = refreshRes.tokens.access_token;
    } else if (!refreshRes.transient) {
      return {
        response: new Response(
          JSON.stringify({
            type: "about:blank",
            title: "Session expired",
            status: 401,
            code: refreshRes.code ?? "TOKEN_EXPIRED",
            detail: "Please sign in again",
          }),
          {
            status: 401,
            headers: { "Content-Type": "application/problem+json" },
          }
        ),
        refreshedTokens: null,
        shouldClearCookies: true,
      };
    }
  }

  const doFetch = async (token: string | undefined) => {
    const headers = new Headers(init.headers);
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return fetch(`${getApiBaseUrl()}${backendPathWithQuery}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  };

  let res: Response;
  try {
    res = await doFetch(accessToken);
  } catch (err) {
    return {
      response: new Response(
        JSON.stringify({
          type: "about:blank",
          title: "Backend unavailable",
          status: 503,
          code: "BACKEND_UNAVAILABLE",
          detail:
            err instanceof Error
              ? `Could not reach API server: ${err.message}`
              : "Could not reach API server",
        }),
        {
          status: 503,
          headers: { "Content-Type": "application/problem+json" },
        }
      ),
      refreshedTokens,
      shouldClearCookies: false,
    };
  }

  // Fallback retry if FastAPI still rejected access token and we have not refreshed yet
  if (res.status === 401 && !attemptedRefresh && refreshToken) {
    const refreshRes = await refreshSessionSingleFlight(refreshToken);
    if (refreshRes.ok) {
      refreshedTokens = refreshRes.tokens;
      accessToken = refreshRes.tokens.access_token;
      res = await doFetch(accessToken);
    } else if (!refreshRes.transient) {
      return {
        response: res,
        refreshedTokens: null,
        shouldClearCookies: true,
      };
    }
  }

  return {
    response: res,
    refreshedTokens,
    shouldClearCookies: false,
  };
}
