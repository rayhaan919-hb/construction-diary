/**
 * Edge-safe JWT expiration inspector. Does not verify signature (FastAPI verifies);
 * used only to proactively refresh expired access tokens in middleware.
 */
export function parseJwtExp(token: string): number | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3 || !parts[1]) return null;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    const payload = JSON.parse(json) as { exp?: unknown };
    return typeof payload.exp === "number" && Number.isFinite(payload.exp)
      ? payload.exp
      : null;
  } catch {
    return null;
  }
}

export function isJwtExpiredOrExpiring(
  token: string | undefined,
  skewSeconds = 30
): boolean {
  if (!token) return true;
  const exp = parseJwtExp(token);
  if (exp === null) return true;
  const nowSec = Math.floor(Date.now() / 1000);
  return exp <= nowSec + skewSeconds;
}
