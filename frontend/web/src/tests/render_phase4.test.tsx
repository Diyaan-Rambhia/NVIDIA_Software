import React from "react";
import { describe, it, expect } from "vitest";
import { AgentAskResponse, NemotronCallResponse, OpsStatus, OpsParameters } from "@/types/agent";

describe("Phase 4 Agent and Admin Structural & State Rendering", () => {
  it("validates Agent Ask response and step fields structure", () => {
    const mockAgentResp: AgentAskResponse = {
      query: "Audit INFY revenue consistency",
      answer: "INFY reported revenue growth consistent with XBRL filings.",
      duration_ms: 1250,
      total_cost_usd: 0.0024,
      disclaimer: "Educational and research review only.",
      steps: [
        {
          step_number: 1,
          tool_name: "f2_filings",
          input_summary: "symbol=INFY, period=Q1 FY27",
          output_summary: "Matched 5 Ind AS revenue line items",
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

    expect(mockAgentResp.steps.length).toBe(2);
    expect(mockAgentResp.steps[0].status).toBe("success");
    expect(mockAgentResp.steps[1].status).toBe("denied");
    expect(mockAgentResp.steps[0].tool_name).toBe("f2_filings");
  });

  it("validates Nemotron runtime call response structure", () => {
    const mockNemotron: NemotronCallResponse = {
      status: "success",
      alias: "fast",
      model_id: "nvidia/llama-3.1-nemotron-70b-instruct",
      response: "Systemic correlation shift indicates heightened co-movement.",
      unverified_note: "Runtime call verified via live token factory gateway.",
    };

    expect(mockNemotron.alias).toBe("fast");
    expect(mockNemotron.status).toBe("success");
  });

  it("validates Ops status and parameters bounds structure", () => {
    const mockOps: OpsStatus = {
      app_env: "production",
      code_version: "ae0167c",
      python_version: "CPython 3.13.5",
      uptime_seconds: 1845,
      enabled_groups: ["core", "auth", "db", "llm"],
    };

    const mockParams: OpsParameters = {
      parameters: {
        ewma_lambda: {
          type: "float",
          default: 0.94,
          min: 0.8,
          max: 0.99,
          override_allowed: true,
          unit: "decay",
        },
      },
    };

    expect(mockOps.app_env).toBe("production");
    expect(mockParams.parameters.ewma_lambda.default).toBe(0.94);
    expect(mockParams.parameters.ewma_lambda.override_allowed).toBe(true);
  });
});
