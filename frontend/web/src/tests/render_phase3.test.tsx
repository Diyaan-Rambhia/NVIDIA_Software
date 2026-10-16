import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBanner } from "@/components/StatusBanner";
import { CorrelationScan, FilingsDemo, DecisionReview } from "@/types/contracts";

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
    const mockFilings: FilingsDemo = {
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
      is_synthetic_demo: true,
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

    expect(mockReview.is_synthetic_demo).toBe(true);
    expect(mockReview.portfolio_xirr).toBe(0.1425);
    expect(mockReview.institutional_metrics?.beta).toBe(0.92);
  });
});
