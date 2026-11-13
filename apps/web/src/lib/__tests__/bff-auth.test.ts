import { afterEach, describe, expect, it, vi } from "vitest";
import { validateBffPath } from "../bff-path";
import { refreshSessionSingleFlight } from "../server-api";

describe("BFF proxy path validation", () => {
  it("allows valid /v1/* paths and encodes segments", () => {
    expect(validateBffPath(["v1", "projects"])).toBe("/v1/projects");
    expect(
      validateBffPath(["v1", "projects", "123e4567-e89b-12d3-a456-426614174000", "timeline"])
    ).toBe("/v1/projects/123e4567-e89b-12d3-a456-426614174000/timeline");
  });

  it("blocks non-v1 paths, empty segments, traversal, and query/fragment injection", () => {
    expect(validateBffPath(undefined)).toBeNull();
    expect(validateBffPath(["v1"])).toBeNull();
    expect(validateBffPath(["healthz"])).toBeNull();
    expect(validateBffPath(["v2", "projects"])).toBeNull();
    expect(validateBffPath(["v1", "..", "admin"])).toBeNull();
    expect(validateBffPath(["v1", "projects", "id?admin=1"])).toBeNull();
    expect(validateBffPath(["v1", "projects", "id#frag"])).toBeNull();
  });
});

describe("Single-flight refresh deduplication", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("issues only one backend refresh call for concurrent requests sharing the same refresh token", async () => {
    let refreshCalls = 0;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
      refreshCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 25));
      return new Response(
        JSON.stringify({
          access_token: "new_access_1",
          refresh_token: "new_refresh_1",
          access_expires_in: 900,
          refresh_expires_at: "2027-01-13T00:00:00Z",
          user: {
            id: "00000000-0000-4000-8000-000000000001",
            email: "owner@example.com",
            full_name: "Site Owner",
            role: "OWNER",
            preferred_locale: "en",
            must_change_password: false,
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    });

    const [r1, r2, r3] = await Promise.all([
      refreshSessionSingleFlight("refresh_token_abc"),
      refreshSessionSingleFlight("refresh_token_abc"),
      refreshSessionSingleFlight("refresh_token_abc"),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(refreshCalls).toBe(1);
    expect(r1.ok && r1.tokens.access_token).toBe("new_access_1");
    expect(r2.ok && r2.tokens.refresh_token).toBe("new_refresh_1");
    expect(r3.ok && r3.tokens.access_token).toBe("new_access_1");
  });
});
