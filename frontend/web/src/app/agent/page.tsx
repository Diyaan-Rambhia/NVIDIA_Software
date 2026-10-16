"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { AgentAskResponse, AgentStep, NemotronCallResponse } from "@/types/agent";
import { StatusBanner } from "@/components/StatusBanner";
import { formatDecimal } from "@/lib/formatters";
import styles from "./agent.module.css";

export default function AgentPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  // Agent Loop states
  const [query, setQuery] = useState("");
  const [maxSteps, setMaxSteps] = useState<number | "">("");
  const [budgetUsd, setBudgetUsd] = useState<number | "">("");
  const [asking, setAsking] = useState(false);
  const [agentResponse, setAgentResponse] = useState<AgentAskResponse | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [agentHttpStatus, setAgentHttpStatus] = useState<number | null>(null);

  // Nemotron Runtime Call states
  const [nemotronPrompt, setNemotronPrompt] = useState("");
  const [nemotronAlias, setNemotronAlias] = useState("fast");
  const [nemotronCalling, setNemotronCalling] = useState(false);
  const [nemotronResponse, setNemotronResponse] = useState<NemotronCallResponse | null>(null);
  const [nemotronError, setNemotronError] = useState<string | null>(null);
  const [nemotronStatus, setNemotronStatus] = useState<number | null>(null);

  const handleAgentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setAsking(true);
    setAgentError(null);
    setAgentHttpStatus(null);
    setAgentResponse(null);

    try {
      const payload = {
        query: query.trim(),
        max_steps: maxSteps === "" ? null : Number(maxSteps),
        budget_usd: budgetUsd === "" ? null : Number(budgetUsd),
      };

      const res = await apiFetch<AgentAskResponse>("/agent/ask", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setAgentResponse(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          router.push("/login");
          return;
        }
        setAgentHttpStatus(err.status);
        setAgentError(err.parsed.message);
      } else {
        setAgentHttpStatus(500);
        setAgentError("Execution error communicating with autonomous agent loop.");
      }
    } finally {
      setAsking(false);
    }
  };

  const handleNemotronSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nemotronPrompt.trim()) return;

    setNemotronCalling(true);
    setNemotronError(null);
    setNemotronStatus(null);
    setNemotronResponse(null);

    try {
      const res = await apiFetch<NemotronCallResponse>("/llm/runtime_call", {
        method: "POST",
        body: JSON.stringify({
          prompt: nemotronPrompt.trim(),
          alias: nemotronAlias,
        }),
      });

      setNemotronResponse(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setNemotronStatus(err.status);
        setNemotronError(err.parsed.message);
      } else {
        setNemotronStatus(503);
        setNemotronError("Nemotron call failed: service unreachable.");
      }
    } finally {
      setNemotronCalling(false);
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>AUTONOMOUS AGENT ORCHESTRATION</span>
        <h1>Multi-Step Analytical Agent & Nemotron Runtime</h1>
        <p className={styles.lead}>
          Executes controlled multi-step tool loops across systemic contagion, XBRL filings,
          and forensic portfolio analytics with strict budget guards and financial advice prevention.
        </p>
      </div>

      <div className={styles.layoutGrid}>
        {/* Main Agent Column */}
        <div className={styles.mainCol}>
          <section className={styles.card}>
            <h2>Autonomous Agent Query Box</h2>
            <p className={styles.cardLead}>
              Ask cross-functional financial questions. The agent breaks down the problem, executes
              analytical tools with entitlement checks, and validates the final response.
            </p>

            {agentError && (
              <StatusBanner
                status={agentHttpStatus}
                message={agentError}
                type={agentHttpStatus === 402 || agentHttpStatus === 403 || agentHttpStatus === 429 ? "warn" : "error"}
              />
            )}

            <form onSubmit={handleAgentSubmit} className={styles.form}>
              <div className={styles.field}>
                <label htmlFor="agent-query">Financial Research Question</label>
                <textarea
                  id="agent-query"
                  rows={3}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. Audit INFY revenue consistency in Q1 FY27 and evaluate portfolio beta sensitivity"
                  required
                  disabled={asking}
                />
              </div>

              <div className={styles.guardRow}>
                <div className={styles.fieldSmall}>
                  <label htmlFor="agent-steps">Max Step Limit (Optional)</label>
                  <input
                    id="agent-steps"
                    type="number"
                    min={1}
                    max={20}
                    value={maxSteps}
                    onChange={(e) => setMaxSteps(e.target.value === "" ? "" : Number(e.target.value))}
                    placeholder="e.g. 5"
                    disabled={asking}
                  />
                </div>

                <div className={styles.fieldSmall}>
                  <label htmlFor="agent-budget">Budget Guard USD (Optional)</label>
                  <input
                    id="agent-budget"
                    type="number"
                    step="0.01"
                    min={0.01}
                    value={budgetUsd}
                    onChange={(e) => setBudgetUsd(e.target.value === "" ? "" : Number(e.target.value))}
                    placeholder="e.g. 0.50"
                    disabled={asking}
                  />
                </div>
              </div>

              <button type="submit" className={styles.submitBtn} disabled={asking}>
                {asking ? "Executing Agent Tool Loop..." : "Execute Agent Loop"}
              </button>
            </form>
          </section>

          {/* Agent Results: Steps & Final Answer */}
          {agentResponse && (
            <div className={styles.resultsWrapper}>
              {/* Step Execution Telemetry */}
              <section className={styles.card}>
                <div className={styles.stepsHeader}>
                  <h2>Executed Tool Steps ({agentResponse.steps.length})</h2>
                  <div className={styles.telemetryBadges} data-mono>
                    <span>COST: ${formatDecimal(agentResponse.total_cost_usd, 4)}</span>
                    <span>DURATION: {agentResponse.duration_ms} ms</span>
                  </div>
                </div>

                <div className={styles.stepsTableWrapper}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Tool Name</th>
                        <th>Input Summary</th>
                        <th>Output Summary</th>
                        <th>Status</th>
                        <th>Cost USD</th>
                        <th>Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agentResponse.steps.map((step: AgentStep) => (
                        <tr key={step.step_number}>
                          <td data-mono className={styles.stepNum}>{step.step_number}</td>
                          <td data-mono className={styles.toolCell}>{step.tool_name}</td>
                          <td className={styles.summaryCell}>{step.input_summary}</td>
                          <td className={styles.summaryCell}>{step.output_summary}</td>
                          <td>
                            <span
                              className={`${styles.statusBadge} ${
                                step.status === "success"
                                  ? styles.badgeSuccess
                                  : step.status === "denied"
                                  ? styles.badgeDenied
                                  : styles.badgeError
                              }`}
                              data-mono
                            >
                              {step.status.toUpperCase()}
                            </span>
                          </td>
                          <td data-mono>${formatDecimal(step.est_cost_usd, 4)}</td>
                          <td data-mono>{step.duration_ms}ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Final Synthesis Answer */}
              <section className={styles.card}>
                <h2>Synthesized Final Answer</h2>
                <div className={styles.answerText}>{agentResponse.answer}</div>
                {agentResponse.disclaimer && (
                  <div className={styles.disclaimer}>{agentResponse.disclaimer}</div>
                )}
              </section>
            </div>
          )}
        </div>

        {/* Runtime Nemotron Endpoint Panel */}
        <div className={styles.sideCol}>
          <section className={styles.nemotronCard}>
            <div className={styles.nemotronHeader}>
              <span className={styles.nemotronBadge} data-mono>NEBIUS TOKEN FACTORY</span>
              <h3>Nemotron Runtime Call</h3>
            </div>
            <p className={styles.nemotronLead}>
              Direct budget-guarded endpoint for testing live NVIDIA Nemotron model inference.
            </p>

            {nemotronError && (
              <StatusBanner
                status={nemotronStatus}
                message={nemotronError}
                type="warn"
              />
            )}

            {nemotronResponse && (
              <div className={styles.nemotronSuccess}>
                <div className={styles.modelMeta} data-mono>
                  MODEL: {nemotronResponse.model_id} ({nemotronResponse.alias})
                </div>
                <div className={styles.rawOutput}>{nemotronResponse.response}</div>
                {nemotronResponse.unverified_note && (
                  <div className={styles.unverifiedNote} data-mono>
                    {nemotronResponse.unverified_note}
                  </div>
                )}
              </div>
            )}

            <form onSubmit={handleNemotronSubmit} className={styles.form}>
              <div className={styles.field}>
                <label htmlFor="nemotron-alias">Model Alias</label>
                <select
                  id="nemotron-alias"
                  value={nemotronAlias}
                  onChange={(e) => setNemotronAlias(e.target.value)}
                  disabled={nemotronCalling}
                >
                  <option value="fast">Fast (Llama-3.1-Nemotron-70B)</option>
                  <option value="mid">Mid (Nemotron-70B-Instruct)</option>
                  <option value="deep">Deep (Nemotron Large)</option>
                </select>
              </div>

              <div className={styles.field}>
                <label htmlFor="nemotron-prompt">Prompt</label>
                <textarea
                  id="nemotron-prompt"
                  rows={3}
                  value={nemotronPrompt}
                  onChange={(e) => setNemotronPrompt(e.target.value)}
                  placeholder="Ask a specific query to the Nemotron endpoint..."
                  required
                  disabled={nemotronCalling}
                />
              </div>

              <button
                type="submit"
                className={styles.nemotronBtn}
                disabled={nemotronCalling}
              >
                {nemotronCalling ? "Calling Runtime..." : "Send Runtime Call"}
              </button>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}
