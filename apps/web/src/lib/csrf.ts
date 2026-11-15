import type { NextRequest } from "next/server";

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Validates same-origin CSRF guarantees on state-changing Route Handler requests.
 * Checks Sec-Fetch-Site and matches Origin / Referer host against Host/X-Forwarded-Host.
 */
export function verifySameOriginRequest(req: NextRequest): boolean {
  if (!MUTATING_METHODS.has(req.method.toUpperCase())) {
    return true;
  }

  const fetchSite = req.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
    return false;
  }

  const expectedHost = (
    req.headers.get("x-forwarded-host") ??
    req.headers.get("host") ??
    req.nextUrl.host
  )
    .split(",")[0]
    ?.trim()
    .toLowerCase();

  const origin = req.headers.get("origin");
  if (origin) {
    try {
      const originHost = new URL(origin).host.toLowerCase();
      return Boolean(expectedHost) && originHost === expectedHost;
    } catch {
      return false;
    }
  }

  const referer = req.headers.get("referer");
  if (referer) {
    try {
      const refHost = new URL(referer).host.toLowerCase();
      return Boolean(expectedHost) && refHost === expectedHost;
    } catch {
      return false;
    }
  }

  // Allow non-browser API/test clients that do not attach Origin/Referer/cross-site headers
  return true;
}
