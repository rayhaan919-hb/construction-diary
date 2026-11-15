import { describe, expect, it } from "vitest";
import {
  buildContentSecurityPolicy,
  resolveLoopbackMediaOrigin,
} from "../csp";

describe("CSP policy builder", () => {
  it("keeps strict HTTPS-only media/image policy for production API URLs", () => {
    const csp = buildContentSecurityPolicy(["https://api.sitediary.example"]);
    expect(csp).toContain("img-src 'self' data: blob: https:;");
    expect(csp).toContain("media-src 'self' data: blob: https:;");
    expect(csp).not.toContain("http://");
  });

  it("refuses arbitrary remote http origins", () => {
    expect(resolveLoopbackMediaOrigin(["http://10.0.0.5:8000"])).toBeNull();
    expect(resolveLoopbackMediaOrigin(["http://api.sitediary.internal:8000"])).toBeNull();
    const csp = buildContentSecurityPolicy(["http://evil.com"]);
    expect(csp).not.toContain("evil.com");
    expect(csp).not.toContain("http://");
  });

  it("permits only the exact local loopback origin in local/Docker deployments", () => {
    const csp = buildContentSecurityPolicy(["http://127.0.0.1:8000"]);
    expect(csp).toContain("img-src 'self' data: blob: https: http://127.0.0.1:8000;");
    expect(csp).toContain("media-src 'self' data: blob: https: http://127.0.0.1:8000;");
  });
});
