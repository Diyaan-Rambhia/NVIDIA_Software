import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FilingsPage from "@/app/filings/page";

// Mock AuthContext
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    sessionChecked: true,
    user: { user_id: "test_user", plan: "institutional" },
  }),
}));

// Mock router
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock apiFetch
const mockApiFetch = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiFetch: (...args: any[]) => mockApiFetch(...args),
  };
});

describe("Filings Calendar Picker & Missing Quarter Rendering", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiFetch.mockImplementation(async (path: string) => {
      if (path.includes("/f2/top50")) {
        return [
          { symbol: "RELIANCE", name: "Reliance Industries Limited" },
          { symbol: "TCS", name: "Tata Consultancy Services Limited" },
        ];
      }
      return [];
    });
  });

  it("renders picker year list starting at FY01 (2001)", async () => {
    render(<FilingsPage />);

    const yearSelect = await screen.findByLabelText(/Fiscal Year:/i);
    expect(yearSelect).toBeDefined();

    // Check that FY01 (2001) exists in the options
    const options = screen.getAllByRole("option") as HTMLOptionElement[];
    const fy01Option = options.find((opt) => opt.value === "2001");
    expect(fy01Option).toBeDefined();
    expect(fy01Option?.textContent).toContain("FY01");
    expect(fy01Option?.textContent).toContain("2001");
  });

  it("renders quarter buttons with correct months text", async () => {
    render(<FilingsPage />);

    expect(screen.getByText("Apr–Jun")).toBeDefined();
    expect(screen.getByText("Jul–Sep")).toBeDefined();
    expect(screen.getByText("Oct–Dec")).toBeDefined();
    expect(screen.getByText("Jan–Mar")).toBeDefined();
  });

  it("renders Annual button with full FY text", async () => {
    render(<FilingsPage />);

    const annualBtn = screen.getByRole("button", { name: /annual/i });
    expect(annualBtn).toBeDefined();
    expect(screen.getByText("Full FY")).toBeDefined();
  });

  it("disables future quarters for upcoming periods", async () => {
    render(<FilingsPage />);

    // In FY 2027 (current local calendar), Q4 is in Jan-Mar 2027 (future)
    // Find Q4 button
    const q4Button = screen.getByRole("button", { name: /q4/i });
    // If today is in Q3, Q4 must be disabled
    const month = new Date().getMonth();
    if (month >= 3 && month <= 11) {
      // Apr - Dec: Q4 (Jan-Mar) is future
      expect(q4Button.hasAttribute("disabled")).toBe(true);
    }
  });

  it("renders missing-quarter notice with machine-readable disclaimer and available quarters", async () => {
    const { ApiError } = await import("@/lib/api");

    mockApiFetch.mockImplementation(async (path: string) => {
      if (path.includes("/f2/top50")) {
        return [{ symbol: "INFY", name: "Infosys Limited" }];
      }
      if (path.includes("/f2/lookup")) {
        const error = new ApiError(
          404,
          {
            code: "period_not_found",
            message: "No data for INFY in Q1 FY27.",
            status: 404,
            available_periods: ["Q1 FY24", "Q2 FY24"],
          } as any,
          null
        );
        throw error;
      }
      return [];
    });

    render(<FilingsPage />);

    // Type company symbol
    const input = screen.getByPlaceholderText(/type company symbol or name/i);
    fireEvent.change(input, { target: { value: "INFY" } });

    // Click Show
    const showBtn = screen.getByRole("button", { name: /^Show$/i });
    fireEvent.click(showBtn);

    await waitFor(() => {
      expect(screen.getByTestId("missing-quarter-notice")).toBeDefined();
    });

    expect(
      screen.getByText(/No data for INFY in/i)
    ).toBeDefined();
    expect(
      screen.getByText(/The source may not hold machine-readable results for older quarters\./i)
    ).toBeDefined();
    expect(
      screen.getByText(/Q1 FY24, Q2 FY24/)
    ).toBeDefined();
  });

  it("renders missing-quarter notice without available quarters when none exist", async () => {
    const { ApiError } = await import("@/lib/api");

    mockApiFetch.mockImplementation(async (path: string) => {
      if (path.includes("/f2/top50")) {
        return [{ symbol: "XYZ", name: "XYZ Corp" }];
      }
      if (path.includes("/f2/lookup")) {
        const error = new ApiError(
          404,
          {
            code: "period_not_found",
            message: "No data for XYZ in Q1 FY05.",
            status: 404,
            available_periods: [],
          } as any,
          null
        );
        throw error;
      }
      return [];
    });

    render(<FilingsPage />);

    const input = screen.getByPlaceholderText(/type company symbol or name/i);
    fireEvent.change(input, { target: { value: "XYZ" } });

    const showBtn = screen.getByRole("button", { name: /^Show$/i });
    fireEvent.click(showBtn);

    await waitFor(() => {
      expect(screen.getByTestId("missing-quarter-notice")).toBeDefined();
    });

    expect(screen.getByText(/No data for XYZ in/i)).toBeDefined();
    expect(
      screen.getByText(/The source may not hold machine-readable results for older quarters\./i)
    ).toBeDefined();
    // Must NOT show available quarters list if empty
    expect(screen.queryByText(/Available quarters for this company/i)).toBeNull();
  });

  it("renders company search suggestions dynamically when typing at least 2 characters", async () => {
    mockApiFetch.mockImplementation(async (path: string) => {
      if (path.includes("/f2/top50")) {
        return [{ symbol: "RELIANCE", name: "Reliance Industries Limited" }];
      }
      if (path.includes("/f2/search?q=TA")) {
        return [
          { symbol: "TATASTEEL", name: "Tata Steel Limited" },
          { symbol: "TATAMOTORS", name: "Tata Motors Limited" },
        ];
      }
      return [];
    });

    render(<FilingsPage />);

    const input = screen.getByPlaceholderText(/type company symbol or name/i);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "TA" } });

    await waitFor(() => {
      expect(screen.getByText("TATASTEEL")).toBeDefined();
      expect(screen.getByText("Tata Steel Limited")).toBeDefined();
      expect(screen.getByText("TATAMOTORS")).toBeDefined();
    });
  });

  it("renders real XBRL numbers with units, periods, and claim quote fallback without '-- = --'", async () => {
    mockApiFetch.mockImplementation(async (path: string) => {
      if (path.includes("/f2/top50")) {
        return [{ symbol: "MARUTI", name: "Maruti Suzuki India Limited" }];
      }
      if (path.includes("/f2/lookup")) {
        return {
          symbol: "MARUTI",
          company_name: "Maruti Suzuki India Limited",
          reporting_period: "Q3 FY25",
          requested_period: "Q3 FY25",
          rules_evaluated: [
            {
              rule_id: "R0",
              rule_name: "Stated Number Consistency",
              status: "not_applicable",
              reason: "no management claim text available",
              claim_quote: null,
              claim_text: null,
              metric_name: "Revenue",
              metric_value: 37500,
              metric_unit: "INR_Crore",
              period: "Q3 FY25",
            },
            {
              rule_id: "R1",
              rule_name: "Directional Movement Consistency",
              status: "pass",
              reason: "Revenue growth matches direction",
              claim_quote: "revenue rose to 37500 crore",
              claim_text: "revenue rose to 37500 crore",
              metric_name: "Revenue",
              metric_value: 37500,
              metric_unit: "INR_Crore",
              period: "Q3 FY25",
            },
          ],
        };
      }
      return [];
    });

    render(<FilingsPage />);

    const input = screen.getByPlaceholderText(/type company symbol or name/i);
    fireEvent.change(input, { target: { value: "MARUTI" } });

    const showBtn = screen.getByRole("button", { name: /^Show$/i });
    fireEvent.click(showBtn);

    await waitFor(() => {
      expect(screen.getAllByText(/Revenue: 37,500 INR_Crore \(Q3 FY25\)/i).length).toBe(2);
    });

    // Check that fallback quote text is rendered
    expect(screen.getByText("No management claim text for this period.")).toBeDefined();

    // Check that actual quote is rendered
    expect(screen.getByText(/“revenue rose to 37500 crore”/i)).toBeDefined();

    // Check that reason is rendered
    expect(screen.getByText("no management claim text available")).toBeDefined();

    // Check that "-- = --" is NEVER present in document
    expect(screen.queryByText(/-- = --/)).toBeNull();
  });
});

