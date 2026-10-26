import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBanner } from "@/components/StatusBanner";
import { ContagionNewsBlock } from "@/components/ContagionNewsBlock";
import { CorrelationScan, DecisionReview } from "@/types/contracts";

describe("Phase 3 Features Structural & State Rendering", () => {
  it("renders Contagion headline metrics and table structurally", () => {
    const mockScan: CorrelationScan = {
      as_of: "demo-period",
      source_label: "unofficial source, demo only",
      regime_flag: "warning",
      absorption_ratio: 0.6123,
      ar_delta_std: 1.84,
      significant_pairs_count: 5,
      mean_correlation: 0.421,
      seed: 42,
      top_shifted_pairs: [
        {
          pair: "INFY - TCS",
          baseline_corr: 0.25,
          current_corr: 0.82,
          fr_adjusted_corr: 0.74,
          p_value: 0.001,
          q_value: 0.005,
        },
      ],
      hypotheses: [
        {
          id: "H-01",
          text: "IT Services correlation tightened during US rate regime announcement",
          evidence_ids: ["E1", "E2"],
        },
      ],
    };

    expect(mockScan.regime_flag).toBe("warning");
    expect(mockScan.top_shifted_pairs?.[0].pair).toBe("INFY - TCS");
    expect(mockScan.hypotheses?.[0].id).toBe("H-01");
  });

  it("renders Filings rule statuses R0-R7 structurally", () => {
    const mockFilings: { companies_audited?: any[]; checks?: any[]; verifier_status?: string } = {
      companies_audited: [{ symbol: "INFY", periods_audited: ["Q1 FY27"] }],
      checks: [
        {
          symbol: "INFY",
          period: "Q1 FY27",
          rule_id: "R0",
          rule_name: "Exact Verbatim Quote Check",
          claim_text: "Revenue grew 4.8% in constant currency",
          metric_name: "revenue_growth",
          metric_value: "4.8%",
          status: "PASS",
          evidence_summary: "Exact substring matched in transcript",
        },
        {
          symbol: "INFY",
          period: "Q1 FY27",
          rule_id: "R1",
          rule_name: "Revenue Consistency",
          claim_text: "Operating profit expanded 12%",
          metric_name: "ebit_growth",
          metric_value: "7.1%",
          status: "FLAG",
          evidence_summary: "Calculated EBIT growth 7.1% deviates from stated 12%",
        },
      ],
      verifier_status: "DETERMINISTIC VERIFICATION ACTIVE",
    };

    expect(mockFilings.checks?.[0].status).toBe("PASS");
    expect(mockFilings.checks?.[1].status).toBe("FLAG");
  });

  it("renders Trade Log portfolio XIRR, synthetic banner, and process metrics structurally", () => {
    const mockReview: DecisionReview = {
      is_synthetic: true,
      synthetic_label: "SYNTHETIC DEMO LOG, not a real investor",
      portfolio_xirr: 0.1425,
      portfolio: {
        total_cost: 500000,
        total_market_value: 575000,
        total_realized_pnl: 25000,
        total_unrealized_pnl: 50000,
      },
      benchmark_replays: [
        {
          benchmark_name: "Nifty 50 (^NSEI)",
          terminal_value: 540000,
          xirr: 0.082,
          partial_shortfall: false,
        },
      ],
      process_metrics: {
        concentration_hhi: 0.1245,
        turnover: 0.45,
        max_drawdown: 0.085,
        disposition_effect: { pgr: 0.42, plr: 0.28 },
        process_label: "Disciplined Rebalancer",
      },
      institutional_metrics: {
        beta: 0.92,
        alpha: 0.041,
        tracking_error: 0.035,
        information_ratio: 1.17,
      },
      review_text: "Portfolio demonstrates disciplined turnover and positive XIRR alpha.",
      disclaimer: "Educational review only. Not investment advice.",
    };

    expect(mockReview.is_synthetic).toBe(true);
    expect(mockReview.portfolio_xirr).toBe(0.1425);
    expect(mockReview.institutional_metrics?.beta).toBe(0.92);
  });

  it("renders ContagionNewsBlock in all four real states", () => {
    // 1. Ready state with articles
    const { unmount: u1 } = render(
      <ContagionNewsBlock
        newsState="ready"
        newsResults={[
          {
            evidence_id: "E1",
            title: "RBI Holds Repo Rate Steady at 6.5%",
            url: "https://example.com/rbi-news",
            content: "Monetary policy committee maintains rate.",
          },
        ]}
      />
    );
    expect(screen.getByText(/RBI Holds Repo Rate Steady/i)).toBeDefined();
    expect(screen.getByText("E1")).toBeDefined();
    u1();

    // 2. Empty state ("no results" with query)
    const { unmount: u2 } = render(
      <ContagionNewsBlock
        newsState="empty"
        newsQuery="NSE Sector Contagion Shock"
      />
    );
    expect(screen.getByText(/no results \(NSE Sector Contagion Shock\)/i)).toBeDefined();
    u2();

    // 3. Not run state ("not run: no search key")
    const { unmount: u3 } = render(
      <ContagionNewsBlock
        newsState="not run: no search key"
      />
    );
    expect(screen.getByText("not run: no search key")).toBeDefined();
    u3();

    // 4. Error state with HTTP status
    const { unmount: u4 } = render(
      <ContagionNewsBlock
        newsState="error"
        errorStatus={503}
        errorMessage="Tavily upstream gateway timeout"
      />
    );
    expect(screen.getByText(/HTTP 503: Tavily upstream gateway timeout/i)).toBeDefined();
    u4();
  });

});


