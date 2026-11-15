const LOCAL_LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]"]);

/**
 * Extract the explicit loopback origin when the portal talks to a local HTTP API
 * (dev / Docker Compose / Playwright E2E) without ever loosening remote `https:` enforcement.
 */
export function resolveLoopbackMediaOrigin(
  candidates: Array<string | undefined>
): string | null {
  for (const raw of candidates) {
    if (!raw) continue;
    try {
      const parsed = new URL(raw);
      if (
        parsed.protocol === "http:" &&
        LOCAL_LOOPBACK_HOSTS.has(parsed.hostname.toLowerCase())
      ) {
        return parsed.origin;
      }
    } catch {
      // Ignore invalid URL strings; default strict CSP applies.
    }
  }
  return null;
}

export function buildContentSecurityPolicy(
  candidates: Array<string | undefined> = []
): string {
  const loopbackOrigin = resolveLoopbackMediaOrigin(candidates);
  const mediaSuffix = loopbackOrigin ? ` ${loopbackOrigin}` : "";
  return [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    `img-src 'self' data: blob: https:${mediaSuffix}`,
    `media-src 'self' data: blob: https:${mediaSuffix}`,
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
    "connect-src 'self'",
  ].join("; ");
}
