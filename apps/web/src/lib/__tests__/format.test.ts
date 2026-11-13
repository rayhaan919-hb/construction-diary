import { describe, expect, it } from "vitest";
import {
  formatCountdown,
  formatDateShort,
  formatDurationMs,
  formatTimeInZone,
  getLanguageLabel,
  getTextDirection,
} from "../format";
import { isJwtExpiredOrExpiring, parseJwtExp } from "../jwt";
import { buildCookieHeaderWithUpdates } from "../auth-cookies";

function makeFakeJwt(payload: Record<string, unknown>): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${header}.${body}.fakesig`;
}

describe("format utilities", () => {
  it("formats YYYY-MM-DD deterministically without timezone shift", () => {
    expect(formatDateShort("2026-11-14")).toBe("14 Nov 2026");
    expect(formatDateShort("2026-01-05")).toBe("05 Jan 2026");
  });

  it("formats UTC ISO timestamps in project timezone", () => {
    expect(formatTimeInZone("2026-11-14T09:30:00Z", "Asia/Karachi")).toBe("14:30");
    expect(formatTimeInZone("2026-11-14T09:30:00Z", "UTC")).toBe("09:30");
  });

  it("formats permit countdown labels", () => {
    expect(formatCountdown(-3)).toBe("3d overdue");
    expect(formatCountdown(0)).toBe("Expires today");
    expect(formatCountdown(1)).toBe("1d left");
    expect(formatCountdown(14)).toBe("14d left");
  });

  it("formats audio duration cleanly", () => {
    expect(formatDurationMs(null)).toBe("—");
    expect(formatDurationMs(65000)).toBe("01:05");
  });

  it("detects RTL direction for Urdu and Arabic", () => {
    expect(getTextDirection("ur", "آج 14 مزدور")).toBe("rtl");
    expect(getTextDirection("ar", null)).toBe("rtl");
    expect(getTextDirection("en", "Foundation pour complete")).toBe("ltr");
    expect(getTextDirection(null, "مزدوروں نے کام مکمل کیا")).toBe("rtl");
    expect(getLanguageLabel("ur")).toBe("Urdu");
  });
});

describe("JWT and cookie helpers", () => {
  it("detects valid, expiring, and malformed JWT tokens", () => {
    const now = Math.floor(Date.now() / 1000);
    const valid = makeFakeJwt({ exp: now + 600 });
    const expiringSoon = makeFakeJwt({ exp: now + 10 });
    const expired = makeFakeJwt({ exp: now - 60 });

    expect(parseJwtExp(valid)).toBe(now + 600);
    expect(isJwtExpiredOrExpiring(valid, 30)).toBe(false);
    expect(isJwtExpiredOrExpiring(expiringSoon, 30)).toBe(true);
    expect(isJwtExpiredOrExpiring(expired, 30)).toBe(true);
    expect(isJwtExpiredOrExpiring("not-a-jwt", 30)).toBe(true);
    expect(isJwtExpiredOrExpiring(undefined, 30)).toBe(true);
  });

  it("rebuilds cookie header with updated and deleted entries", () => {
    const header = buildCookieHeaderWithUpdates(
      [
        { name: "sd_access", value: "old_access" },
        { name: "sd_refresh", value: "old_refresh" },
        { name: "sd_must_change", value: "1" },
        { name: "other", value: "keep" },
      ],
      {
        sd_access: "new_access",
        sd_refresh: "new_refresh",
        sd_must_change: null,
      }
    );

    expect(header).toContain("sd_access=new_access");
    expect(header).toContain("sd_refresh=new_refresh");
    expect(header).toContain("other=keep");
    expect(header).not.toContain("sd_must_change");
    expect(header).not.toContain("old_access");
  });
});
