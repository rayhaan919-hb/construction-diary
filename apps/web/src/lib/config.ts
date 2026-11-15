export const ACCESS_COOKIE_NAME = "sd_access";
export const REFRESH_COOKIE_NAME = "sd_refresh";
export const MUST_CHANGE_COOKIE_NAME = "sd_must_change";

export const DEFAULT_ACCESS_TTL_SECONDS = 900;
export const REFRESH_TTL_SECONDS = 60 * 60 * 24 * 60; // 60 days

export function getApiBaseUrl(): string {
  const raw = process.env.API_BASE_URL ?? "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

export function isSessionCookieSecure(): boolean {
  if (process.env.SESSION_COOKIE_SECURE !== undefined) {
    return process.env.SESSION_COOKIE_SECURE === "true";
  }
  return process.env.NODE_ENV === "production";
}

export function isDemoMode(): boolean {
  if (
    process.env.NODE_ENV === "production" &&
    process.env.ALLOW_DEMO_IN_PRODUCTION !== "true"
  ) {
    return false;
  }
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

export function getEdgeJwtSecret(): string | null {
  const secret = process.env.JWT_SECRET_KEY ?? process.env.JWT_SECRET ?? "";
  return secret.trim().length > 0 ? secret.trim() : null;
}
