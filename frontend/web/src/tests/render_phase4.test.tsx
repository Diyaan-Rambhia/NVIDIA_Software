import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AgentPage from "@/app/agent/page";
import ContagionPage from "@/app/contagion/page";
import FilingsPage from "@/app/filings/page";
import AdminPage from "@/app/admin/page";
import * as apiModule from "@/lib/api";
import { ApiError } from "@/lib/api";
import { AgentAskResponse } from "@/types/agent";

const mockPush = vi.fn();
const mockRouter = { push: mockPush };

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "test-user-id", email: "test@example.com", plan: "retail_free" },
    isAuthenticated: true,
    isAdmin: true,
  }),
}));

describe("Phase 4 /agent Chat Page & Tavily Rail Rendering", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockPush.mockReset();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe("Agent Chat Page Rendering", () => {
    it("renders empty state with small title, plan badge, note, and starter chips above input", () => {
      render(<AgentPage />);

      expect(screen.getByText("FinFriend agent")).toBeDefined();
      expect(screen.getByText("retail_free")).toBeDefined();
      expect(screen.getByText("Each question is answered on its own.")).toBeDefined();

      const chips = screen.getByTestId("starter-chips");
      expect(chips).toBeDefined();

      expect(
        screen.getByText("Check systemic absorption ratio and Forbes-Rigobon correlation shifts for Indian equities.")
      ).toBeDefined();
      expect(
        screen.getByText("Audit INFY filings for revenue discrepancies between press releases and XBRL.")
      ).toBeDefined();
      expect(
        screen.getByText("Evaluate portfolio trade logs for XIRR performance and disposition effect.")
      ).toBeDefined();
    });

    it("verifies starter chips position above input box and hides chips when thread has a message", async () => {
      vi.spyOn(apiModule, "apiFetch").mockResolvedValueOnce({
        query: "What is absorption ratio?",
        answer: "Absorption ratio measures the proportion of market variance explained by top eigenvalues.",
        disclaimer: "Educational only.",
        duration_ms: 300,
        total_cost_usd: 0.001,
        steps: [],
      });

      render(<AgentPage />);
      expect(screen.getByTestId("starter-chips")).toBeDefined();

      const textarea = screen.getByPlaceholderText(/Ask a question about contagion/i) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: "What is absorption ratio?" } });
      const sendBtn = screen.getByText("Send");
      fireEvent.click(sendBtn);

      await waitFor(() => {
        expect(
          screen.getByText("Absorption ratio measures the proportion of market variance explained by top eigenvalues.")
        ).toBeDefined();
      });

      // Chips must be hidden once thread contains a message
      expect(screen.queryByTestId("starter-chips")).toBeNull();
    });

    it("renders sending state with plain running line, disabled input, and honest cancel button", async () => {
      vi.spyOn(apiModule, "apiFetch").mockImplementation(
        () => new Promise(() => {}) // pending
      );

      render(<AgentPage />);
      const textarea = screen.getByPlaceholderText(/Ask a question about contagion/i) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: "Test contagion analysis" } });
      const sendBtn = screen.getByText("Send");
      fireEvent.click(sendBtn);

      expect(screen.getByText("running")).toBeDefined();
      expect(textarea.disabled).toBe(true);
      expect(
        screen.getByText("Cancel stops waiting; the server may still finish.")
      ).toBeDefined();
    });

    it("renders answer with steps summary, all step fields, and placeholder label", async () => {
      const mockResponse: AgentAskResponse = {
        query: "Audit INFY revenue consistency",
        answer: "INFY revenue is verified against Ind AS disclosures.",
        disclaimer: "Educational and research review only.",
        duration_ms: 1250,
        total_cost_usd: 0.0024,
        steps: [
          {
            step_number: 1,
            tool_name: "f2_filings",
            input_summary: "symbol=INFY",
            output_summary: "5 line items verified",
            status: "success",
            est_cost_usd: 0.0012,
            duration_ms: 450,
          },
          {
            step_number: 2,
            tool_name: "f1_contagion",
            input_summary: "pair=INFY-TCS",
            output_summary: "Feature 1 denied: institutional tier required",
            status: "denied",
            est_cost_usd: 0.0004,
            duration_ms: 150,
          },
        ],
      };

      vi.spyOn(apiModule, "apiFetch").mockResolvedValue(mockResponse);

      render(<AgentPage />);
      const textarea = screen.getByPlaceholderText(/Ask a question about contagion/i);
      fireEvent.change(textarea, { target: { value: "Audit INFY" } });
      fireEvent.click(screen.getByText("Send"));

      await waitFor(() => {
        expect(screen.getByText("INFY revenue is verified against Ind AS disclosures.")).toBeDefined();
      });

      expect(screen.getAllByText("Balanced").length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("2 steps, $0.0024, 1250ms")).toBeDefined();
      expect(screen.getByText("f2_filings")).toBeDefined();
      expect(screen.getByText("5 line items verified")).toBeDefined();
      expect(screen.getByText("SUCCESS")).toBeDefined();
      expect(screen.getByText("DENIED")).toBeDefined();
      expect(screen.getByText("f1_contagion")).toBeDefined();
      expect(screen.getByText("$0.0012")).toBeDefined();
      expect(screen.getByText("450ms")).toBeDefined();
    });

    it("handles 401 error by redirecting to /login", async () => {
      vi.spyOn(apiModule, "apiFetch").mockRejectedValue(
        new ApiError(401, { status: 401, code: "UNAUTHORIZED", message: "Auth required" }, {})
      );

      render(<AgentPage />);
      const textarea = screen.getByPlaceholderText(/Ask a question about contagion/i);
      fireEvent.change(textarea, { target: { value: "Query 401" } });
      fireEvent.click(screen.getByText("Send"));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith("/login");
      });
    });

    it("renders 402, 403, 429, 503, and agent limit errors as reply blocks", async () => {
      vi.spyOn(apiModule, "apiFetch").mockRejectedValueOnce(
        new ApiError(402, { status: 402, code: "UPGRADE_REQUIRED", message: "Plan upgrade required." }, {})
      );

      render(<AgentPage />);
      const textarea = screen.getByPlaceholderText(/Ask a question about contagion/i);
      fireEvent.change(textarea, { target: { value: "Query 402" } });
      fireEvent.click(screen.getByText("Send"));

      await waitFor(() => {
        expect(screen.getByText(/HTTP 402 \[UPGRADE_REQUIRED\]/i)).toBeDefined();
      });
    });

    it("verifies no web storage is touched by chat operations", () => {
      render(<AgentPage />);
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
      expect(document.cookie).toBe("");
    });
  });

  describe("Contagion Context and Hypotheses Full-Width Layout", () => {
    it("renders Context and hypotheses section between headline metrics and shifted asset pairs", async () => {
      vi.spyOn(apiModule, "apiFetch").mockResolvedValueOnce({
        as_of: "demo-period",
        source_label: "unofficial source, demo only",
        regime_flag: "warning",
        absorption_ratio: 0.582,
        ar_delta_std: 1.65,
        significant_pairs_count: 3,
        mean_correlation: 0.45,
        seed: 42,
        top_shifted_pairs: [
          {
            pair: "INFY - TCS",
            baseline_corr: 0.2,
            current_corr: 0.8,
            fr_adjusted_corr: 0.72,
            p_value: 0.001,
            q_value: 0.004,
          },
        ],
        news: {
          query: "RBI Systemic Risk",
          results: [
            {
              title: "RBI issues financial stability report",
              source: "RBI Bulletin",
              snippet: "Systemic risk indicators remain within acceptable tolerance.",
              url: "https://rbi.org.in/press/2026",
              evidence_id: "E1",
            },
            {
              title: "Internal Unverified Notes",
              source: "Local Wire",
              snippet: "Unencrypted protocol link should not render as anchor tag.",
              url: "http://insecure.internal.bank/report",
            },
          ],
        },
        hypotheses: [
          {
            id: "H1",
            text: "Interbank contagion hypothesis",
            evidence_ids: ["E1"],
          },
        ],
      });

      render(<ContagionPage />);

      await waitFor(() => {
        expect(screen.getByText("ABSORPTION RATIO")).toBeDefined();
      });

      // Context and hypotheses section full width
      expect(screen.getByText("Context and hypotheses")).toBeDefined();
      expect(screen.getByText("Market news. Not investment advice.")).toBeDefined();
      expect(screen.getByText("Query: RBI Systemic Risk")).toBeDefined();
      expect(screen.getByText("RBI issues financial stability report")).toBeDefined();
      expect(screen.getByText("E1")).toBeDefined();

      const anchor = screen.getByRole("link", { name: "RBI issues financial stability report" }) as HTMLAnchorElement;
      expect(anchor.getAttribute("href")).toBe("https://rbi.org.in/press/2026");
      expect(anchor.getAttribute("rel")).toBe("noopener noreferrer");

      expect(screen.getByText("Internal Unverified Notes")).toBeDefined();
      expect(screen.queryByRole("link", { name: "Internal Unverified Notes" })).toBeNull();

      // Check hypotheses
      expect(screen.getByText("Interbank contagion hypothesis")).toBeDefined();

      // Check shifted asset pairs table is present
      expect(screen.getByText("Top Shifted Asset Pairs (Forbes-Rigobon Adjusted)")).toBeDefined();
      expect(screen.getByText("INFY - TCS")).toBeDefined();
    });
  });

  describe("Filings Consistency Search Rendering", () => {
    const mockCompaniesList = [
      { symbol: "INFY", name: "Infosys Limited" },
      { symbol: "ITC", name: "ITC Limited" },
    ];

    const mockLookupResponse = {
      company: "Infosys Limited",
      symbol: "INFY",
      requested_period: "Annual",
      reporting_period: "FY26",
      is_annual: true,
      verified_metrics: {
        RevenueFromOperations: 128260,
        ProfitBeforeTax: 32000,
        ProfitLossForPeriod: 24000,
      },
      rules_evaluated: [
        {
          rule_id: "R0",
          status: "pass",
          claim_text: "Revenue grew 5%",
          metric_name: "RevenueFromOperations",
          metric_value: 128260,
          evidence_summary: "Exact quote match verified",
        },
        {
          rule_id: "R1",
          status: "pass",
          claim_text: "Revenue consistent",
          metric_name: "growth",
          metric_value: 0.05,
          evidence_summary: "Consistent within tolerance",
        },
      ],
      source: "official NSE Ind AS XBRL archive",
    };

    it("renders search section with text field, quarter selector, and Show button", async () => {
      vi.spyOn(apiModule, "apiFetch").mockResolvedValueOnce(mockCompaniesList);

      render(<FilingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Find Company:/i)).toBeDefined();
      });

      expect(screen.getByLabelText(/Fiscal Year:/i)).toBeDefined();
      expect(screen.getByRole("button", { name: "Show" })).toBeDefined();
      expect(screen.getByText("Annual")).toBeDefined();
    });

    it("displays result for a known company and period", async () => {
      vi.spyOn(apiModule, "apiFetch").mockImplementation((url: string) => {
        if (url.includes("/f2/companies") || url.includes("/f2/top50")) return Promise.resolve(mockCompaniesList);
        if (url.includes("/f2/lookup")) return Promise.resolve(mockLookupResponse);
        return Promise.reject(new Error("Unknown route"));
      });

      render(<FilingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Find Company:/i)).toBeDefined();
      });

      const input = screen.getByLabelText(/Find Company:/i);
      fireEvent.change(input, { target: { value: "INFY" } });
      const annualBtn = screen.getByRole("button", { name: /annual/i });
      fireEvent.click(annualBtn);
      const showBtn = screen.getByRole("button", { name: "Show" });

      fireEvent.click(showBtn);

      await waitFor(() => {
        expect(screen.getByTestId("filings-search-result")).toBeDefined();
      });

      const resultSection = screen.getByTestId("filings-search-result");
      expect(resultSection.textContent).toContain("Infosys Limited");
      expect(screen.getByText("Exact Verbatim Quote Check")).toBeDefined();
      expect(screen.getByText("Revenue Consistency")).toBeDefined();
    });

    it("handles an unknown company search error", async () => {
      vi.spyOn(apiModule, "apiFetch").mockImplementation((url: string) => {
        if (url.includes("/f2/companies") || url.includes("/f2/top50")) return Promise.resolve(mockCompaniesList);
        if (url.includes("/f2/lookup")) {
          return Promise.reject(
            new ApiError(404, {
              status: 404,
              code: "company_not_found",
              message: "Company 'UNKNOWN' not found in official NSE equity list",
            }, null)
          );
        }
        return Promise.reject(new Error("Unknown route"));
      });

      render(<FilingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Find Company:/i)).toBeDefined();
      });

      const input = screen.getByLabelText(/Find Company:/i);
      fireEvent.change(input, { target: { value: "UNKNOWN" } });
      const showBtn = screen.getByRole("button", { name: "Show" });
      fireEvent.click(showBtn);

      await waitFor(() => {
        expect(
          screen.getByText("Company 'UNKNOWN' not found in official NSE equity list")
        ).toBeDefined();
      });
    });

    it("handles an unavailable period search error", async () => {
      vi.spyOn(apiModule, "apiFetch").mockImplementation((url: string) => {
        if (url.includes("/f2/companies") || url.includes("/f2/top50")) return Promise.resolve(mockCompaniesList);
        if (url.includes("/f2/lookup")) {
          return Promise.reject(
            new ApiError(404, {
              status: 404,
              code: "period_not_found",
              message: "no data for INFY in Q4 FY28. Available periods: ['Annual']",
            }, null)
          );
        }
        return Promise.reject(new Error("Unknown route"));
      });

      render(<FilingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Find Company:/i)).toBeDefined();
      });

      const input = screen.getByLabelText(/Find Company:/i);
      fireEvent.change(input, { target: { value: "INFY" } });
      const annualBtn = screen.getByRole("button", { name: /annual/i });
      fireEvent.click(annualBtn);
      const showBtn = screen.getByRole("button", { name: "Show" });
      fireEvent.click(showBtn);

      await waitFor(() => {
        expect(screen.getByTestId("missing-quarter-notice")).toBeDefined();
      });
      expect(screen.getByText(/No data for INFY in/i)).toBeDefined();
      expect(
        screen.getByText(/The source may not hold machine-readable results for older quarters\./i)
      ).toBeDefined();
    });

    it("shows equity list error if /f2/top50 fails", async () => {
      vi.spyOn(apiModule, "apiFetch").mockRejectedValueOnce(
        new ApiError(502, {
          status: 502,
          code: "source_unavailable",
          message: "Failed to load Nifty 50 constituents: timeout",
        }, null)
      );

      render(<FilingsPage />);

      await waitFor(() => {
        expect(
          screen.getByText("Error loading Nifty 50: Failed to load Nifty 50 constituents: timeout")
        ).toBeDefined();
      });
    });
  });

  describe("Admin Console Configuration States Rendering", () => {
    const mockAdminData = {
      status: { code_version: "abc1234", uptime_seconds: 120 },
      ready: { ready: true, checks: {} },
      health: { status: "ok" },
      config: {
        enabled_groups: ["core", "llm"],
        groups: {
          core: [
            { name: "APP_ENV", present: true, required_when_enabled: true, group_enabled: true },
            { name: "LOG_LEVEL", present: false, required_when_enabled: true, group_enabled: true },
          ],
          search: [
            { name: "TAVILY_API_KEY", present: false, required_when_enabled: true, group_enabled: false },
          ],
          optional: [
            { name: "PINECONE_API_KEY", present: false, required_when_enabled: false, group_enabled: false },
            { name: "SMTP_HOST", present: true, required_when_enabled: false, group_enabled: false },
            { name: "SMTP_USER", present: false, required_when_enabled: false, group_enabled: false },
            { name: "SMTP_PASSWORD", present: false, required_when_enabled: false, group_enabled: false },
          ],
        },
      },
      parameters: { parameters: {} },
      events: [],
      llm: [],
    };

    it("renders admin config states: enabled and missing, not enabled, and hides SMTP_", async () => {
      vi.spyOn(apiModule, "apiFetch").mockImplementation((url: string) => {
        if (url === "/ops/status") return Promise.resolve(mockAdminData.status);
        if (url === "/ready") return Promise.resolve(mockAdminData.ready);
        if (url === "/health") return Promise.resolve(mockAdminData.health);
        if (url === "/ops/config") return Promise.resolve(mockAdminData.config);
        if (url === "/ops/parameters") return Promise.resolve(mockAdminData.parameters);
        if (url === "/ops/activity/events") return Promise.resolve(mockAdminData.events);
        if (url === "/ops/activity/llm") return Promise.resolve(mockAdminData.llm);
        return Promise.reject(new Error("Unknown route"));
      });

      render(<AdminPage />);

      await waitFor(() => {
        expect(screen.getByText("GROUP: CORE")).toBeDefined();
      });

      // APP_ENV: group enabled and present
      expect(screen.getByText("APP_ENV")).toBeDefined();
      expect(screen.getByText("present")).toBeDefined();

      // LOG_LEVEL: group enabled and missing -> shows "missing"
      expect(screen.getByText("LOG_LEVEL")).toBeDefined();
      expect(screen.getByText("missing")).toBeDefined();

      // TAVILY_API_KEY: group NOT enabled -> shows "not used: group not enabled"
      expect(screen.getByText("TAVILY_API_KEY")).toBeDefined();
      const notUsedBadges = screen.getAllByText("not used: group not enabled");
      expect(notUsedBadges.length).toBeGreaterThanOrEqual(1);

      // SMTP_ variables must NOT be displayed
      expect(screen.queryByText("SMTP_HOST")).toBeNull();
      expect(screen.queryByText("SMTP_USER")).toBeNull();
      expect(screen.queryByText("SMTP_PASSWORD")).toBeNull();

      // Non-SMTP variable in optional group is rendered
      expect(screen.getByText("PINECONE_API_KEY")).toBeDefined();
    });
  });
});
