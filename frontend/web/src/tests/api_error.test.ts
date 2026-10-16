import { describe, it, expect } from "vitest";
import { parseApiError } from "@/lib/errors";

describe("parseApiError", () => {
  it("maps 401 unauthorized status cleanly", () => {
    const err = parseApiError(401, { error: { code: "UNAUTHORIZED", message: "Invalid credentials" } });
    expect(err.status).toBe(401);
    expect(err.code).toBe("UNAUTHORIZED");
    expect(err.message).toBe("Invalid credentials");
  });

  it("maps 402 payment required with upgrade targets", () => {
    const err = parseApiError(402, {
      error: {
        code: "UPGRADE_REQUIRED",
        message: "Feature 1 requires institutional plan",
        upgrade_targets: ["institutional_paid"],
      },
    });
    expect(err.status).toBe(402);
    expect(err.upgradeTargets).toEqual(["institutional_paid"]);
  });

  it("maps 403 access denied segment restrictions", () => {
    const err = parseApiError(403, {
      detail: {
        code: "segment_restricted",
        message: "Retail accounts cannot access systemic contagion scanner",
      },
    });
    expect(err.status).toBe(403);
    expect(err.code).toBe("segment_restricted");
    expect(err.message).toContain("Retail accounts");
  });

  it("maps 429 quota exceeded with reset time", () => {
    const err = parseApiError(429, {
      error: {
        code: "QUOTA_EXCEEDED",
        message: "Daily quota exhausted",
        reset_time: "tomorrow 00:00 UTC",
      },
    });
    expect(err.status).toBe(429);
    expect(err.resetTime).toBe("tomorrow 00:00 UTC");
    expect(err.message).toContain("quota");
  });

  it("maps 503 service unavailable with message", () => {
    const err = parseApiError(503, {
      error: {
        code: "provider_not_configured",
        message: "No real LLM provider is configured in production",
      },
    });
    expect(err.status).toBe(503);
    expect(err.code).toBe("provider_not_configured");
    expect(err.message).toContain("No real LLM provider");
  });
});
