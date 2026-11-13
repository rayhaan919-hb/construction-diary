import { getApiBaseUrl } from "./config";
import type { TokenPair } from "./types";

export type RefreshedTokenPair = TokenPair;

export type RefreshResult =
  | { ok: true; tokens: TokenPair }
  | { ok: false; status: number; code?: string; transient: boolean };

/**
 * Edge-safe token refresh helper (used by middleware.ts and Node Route Handlers).
 */
export async function refreshWithBackend(
  refreshToken: string
): Promise<RefreshResult> {
  try {
    const res = await fetch(`${getApiBaseUrl()}/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });

    if (res.ok) {
      const tokens = (await res.json()) as RefreshedTokenPair;
      return { ok: true, tokens };
    }

    let code: string | undefined;
    try {
      const problem = (await res.json()) as { code?: string };
      code = problem.code;
    } catch {
      // ignore non-JSON error
    }

    return {
      ok: false,
      status: res.status,
      code,
      transient: res.status >= 500,
    };
  } catch {
    return { ok: false, status: 503, code: "BACKEND_UNAVAILABLE", transient: true };
  }
}
