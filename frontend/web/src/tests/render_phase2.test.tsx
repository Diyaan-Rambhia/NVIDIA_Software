import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import LandingPage from "@/app/page";
import { StatusBanner } from "@/components/StatusBanner";
import { Footer } from "@/components/Footer";

describe("Phase 2 Structural & State Rendering", () => {
  it("renders Landing page without backend calls", () => {
    render(<LandingPage />);
    expect(screen.getByText(/When diversified assets suddenly move together/i)).toBeDefined();
    expect(screen.getByText(/Illustration, not market data/i)).toBeDefined();
    expect(screen.getByText(/Maths first/i)).toBeDefined();
    expect(screen.getByText(/Unofficial Market Prices:/i)).toBeDefined();
  });

  it("renders Footer with exact educational notice only", () => {
    render(<Footer />);
    expect(screen.getByText("Educational only. Not investment advice.")).toBeDefined();
  });

  it("renders 401 error state", () => {
    render(
      <StatusBanner
        status={401}
        message="Authentication required. Please log in."
        type="error"
      />
    );
    expect(screen.getByText("HTTP 401")).toBeDefined();
    expect(screen.getByText(/Authentication required/i)).toBeDefined();
  });

  it("renders 402 upgrade state with targets", () => {
    render(
      <StatusBanner
        error={{
          status: 402,
          code: "UPGRADE_REQUIRED",
          message: "Feature 1 requires institutional plan",
          upgradeTargets: ["institutional_paid"],
        }}
      />
    );
    expect(screen.getByText("HTTP 402")).toBeDefined();
    expect(screen.getByText(/institutional_paid/i)).toBeDefined();
  });

  it("renders 403 denied state", () => {
    render(
      <StatusBanner
        status={403}
        message="Access denied for your account segment."
        type="warn"
      />
    );
    expect(screen.getByText("HTTP 403")).toBeDefined();
    expect(screen.getByText(/Access denied/i)).toBeDefined();
  });

  it("renders 429 quota state with reset time", () => {
    render(
      <StatusBanner
        error={{
          status: 429,
          code: "QUOTA_EXCEEDED",
          message: "Daily quota exhausted",
          resetTime: "00:00 UTC",
        }}
      />
    );
    expect(screen.getByText("HTTP 429")).toBeDefined();
    expect(screen.getByText(/00:00 UTC/i)).toBeDefined();
  });

  it("renders 503 service unavailable state", () => {
    render(
      <StatusBanner
        status={503}
        message="Service temporarily unavailable: benchmark data is not shipped"
        type="warn"
      />
    );
    expect(screen.getByText("HTTP 503")).toBeDefined();
    expect(screen.getByText(/benchmark data is not shipped/i)).toBeDefined();
  });

  it("renders empty state with reason", () => {
    render(<StatusBanner emptyReason="No trade records found in file" />);
    expect(screen.getByText(/No trade records found/i)).toBeDefined();
  });
});
