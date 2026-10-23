import { describe, it, expect } from "vitest";
import { sanitizeUserFacingText } from "@/lib/sanitizer";

describe("Vendor Names Sanitizer", () => {
  it("replaces Nebius Token Factory with Model service", () => {
    const raw = "Upstream error from Nebius Token Factory: rate limit reached.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/nebius/i);
    expect(clean).not.toMatch(/token factory/i);
    expect(clean).toContain("Model service");
  });

  it("replaces Nemotron with analytical model", () => {
    const raw = "The Nemotron model returned an invalid payload.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/nemotron/i);
    expect(clean).toContain("analytical model");
  });

  it("replaces Tavily with Market news", () => {
    const raw = "Tavily search provider failed to return results.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/tavily/i);
    expect(clean).toContain("Market news");
  });

  it("replaces Supabase with Authentication service", () => {
    const raw = "Failed to connect to Supabase database instance.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/supabase/i);
    expect(clean).toContain("Authentication service");
  });

  it("replaces yfinance with generic third-party market data description", () => {
    const raw = "Failed to fetch price series from yfinance for symbol INFY.NS.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/yfinance/i);
    expect(clean).toContain("market data (third-party, delayed)");
  });

  it("replaces Next.js with Application service", () => {
    const raw = "Unhandled exception in Next.js internal router.";
    const clean = sanitizeUserFacingText(raw);
    expect(clean).not.toMatch(/next\.js/i);
    expect(clean).toContain("Application service");
  });

  it("handles null and empty input gracefully", () => {
    expect(sanitizeUserFacingText(null)).toBe("");
    expect(sanitizeUserFacingText("")).toBe("");
  });
});
