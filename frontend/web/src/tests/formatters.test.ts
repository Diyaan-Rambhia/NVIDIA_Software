import { describe, it, expect } from "vitest";
import { formatINR, formatPercent, formatDecimal, formatBps, truncateString } from "@/lib/formatters";

describe("Formatters", () => {
  it("formats Indian Rupee currency correctly", () => {
    expect(formatINR(123456.78)).toBe("INR 1,23,456.78");
    expect(formatINR(10000000)).toBe("INR 1,00,00,000.00");
    expect(formatINR(null)).toBe("--");
  });

  it("formats percentages correctly", () => {
    expect(formatPercent(0.1234)).toBe("12.34%");
    expect(formatPercent(0.05, 1)).toBe("5.0%");
    expect(formatPercent(null)).toBe("--");
  });

  it("formats decimals and basis points", () => {
    expect(formatDecimal(0.123456, 4)).toBe("0.1235");
    expect(formatBps(0.015)).toBe("150 bps");
    expect(formatBps(null)).toBe("--");
  });

  it("truncates strings gracefully", () => {
    expect(truncateString("Short", 10)).toBe("Short");
    expect(truncateString("This is a longer text that needs to be truncated", 15)).toBe("This is a lo...");
  });
});
