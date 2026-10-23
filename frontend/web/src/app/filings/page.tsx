"use client";

import React, { useEffect, useState, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { StatusBanner } from "@/components/StatusBanner";
import { formatFiscalPeriod, formatINR } from "@/lib/formatters";
import styles from "./filings.module.css";

interface CompanySuggestion {
  symbol: string;
  name: string;
}

interface EvaluatedRuleItem {
  rule_id: string;
  rule_name?: string;
  status: string;
  severity?: string;
  evidence?: any;
  reason?: string | null;
  claim_text?: string;
  metric_name?: string;
  metric_value?: string | number;
  evidence_summary?: string;
  period?: string;
}

interface LookupResult {
  company: string;
  symbol: string;
  requested_period: string;
  reporting_period: string;
  is_annual: boolean;
  verified_metrics: {
    RevenueFromOperations?: number;
    ProfitBeforeTax?: number;
    ProfitLossForPeriod?: number;
    [key: string]: number | undefined;
  };
  rules_evaluated: EvaluatedRuleItem[];
  source: string;
}

const RULE_NAMES: Record<string, string> = {
  R0: "Exact Verbatim Quote Check",
  R1: "Revenue Consistency",
  R2: "Operating Margin Alignment",
  R3: "PAT Growth vs Statement",
  R4: "YoY Trend Inconsistency",
  R5: "Standalone vs Consolidated Mismatch",
  R6: "Unit & Scale Shift",
  R7: "Sector Relative Performance Flag",
};

export default function FilingsPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked } = useAuth();

  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [companies, setCompanies] = useState<CompanySuggestion[]>([]);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedQuarter, setSelectedQuarter] = useState("Annual");
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupResult, setLookupResult] = useState<LookupResult | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupStatus, setLookupStatus] = useState<number | null>(null);

  const routerRef = useRef(router);
  routerRef.current = router;

  // Load official equity suggestions list on mount
  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      routerRef.current.push("/login");
      return;
    }
    if (!isAuthenticated) return;

    let isMounted = true;
    async function loadCompanies() {
      setLoadingCompanies(true);
      setCompaniesError(null);
      try {
        const list = await apiFetch<CompanySuggestion[]>("/f2/companies");
        if (isMounted) {
          setCompanies(Array.isArray(list) ? list : []);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        if (err instanceof ApiError) {
          if (err.status === 401) {
            routerRef.current.push("/login");
            return;
          }
          setCompaniesError(err.parsed.message || `Failed to load official equity list (HTTP ${err.status})`);
        } else {
          setCompaniesError("Failed to connect to backend for official NSE equity list.");
        }
      } finally {
        if (isMounted) setLoadingCompanies(false);
      }
    }

    loadCompanies();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, sessionChecked]);

  // Autocomplete suggestions matching searchQuery from backend list
  const suggestedMatches = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || companies.length === 0) return [];
    return companies
      .filter((c) => c.symbol.toLowerCase().includes(q) || c.name.toLowerCase().includes(q))
      .slice(0, 10);
  }, [searchQuery, companies]);

  const quarterOptions = ["Annual", "Q1 FY27", "Q2 FY27", "Q3 FY27", "Q4 FY27"];

  const handleShowClick = async () => {
    const comp = searchQuery.trim();
    if (!comp) return;

    setLookupLoading(true);
    setLookupError(null);
    setLookupStatus(null);
    setLookupResult(null);

    const periodParam = selectedQuarter.trim() || "Annual";

    try {
      const res = await apiFetch<LookupResult>(
        `/f2/lookup?company=${encodeURIComponent(comp)}&period=${encodeURIComponent(periodParam)}`
      );
      setLookupResult(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          routerRef.current.push("/login");
          return;
        }
        setLookupStatus(err.status);
        setLookupError(err.parsed.message || `Lookup failed with HTTP ${err.status}`);
      } else {
        setLookupStatus(503);
        setLookupError("Network failure executing filings consistency lookup.");
      }
    } finally {
      setLookupLoading(false);
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>FEATURE 02 / FILINGS CONSISTENCY</span>
        <h1>XBRL Statements & Verbatim Quote Verification</h1>
        <p className={styles.lead}>
          Deterministic audit comparing management press releases and earnings transcripts against filed Ind AS XBRL financials.
        </p>
      </div>

      {companiesError && (
        <StatusBanner
          status={503}
          message={`Error loading equity suggestions: ${companiesError}`}
          type="error"
        />
      )}

      {/* Top Search & Filter Section */}
      <section className={styles.searchSection} aria-label="Company Search">
        <div className={styles.searchControlsRow}>
          <div className={styles.searchFieldGroup}>
            <label htmlFor="company-search-input" className={styles.fieldLabel}>
              Find Company:
            </label>
            <div className={styles.inputWithSuggestions}>
              <input
                id="company-search-input"
                type="text"
                className={styles.searchInput}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={loadingCompanies ? "Loading NSE equity list..." : "Type company symbol or name..."}
                list="company-matches-datalist"
                autoComplete="off"
              />
              <datalist id="company-matches-datalist">
                {companies.map((c) => (
                  <option key={c.symbol} value={c.symbol}>
                    {c.name && c.name !== c.symbol ? `${c.symbol} - ${c.name}` : c.symbol}
                  </option>
                ))}
              </datalist>

              {searchQuery.trim() && suggestedMatches.length > 0 && (
                <div className={styles.suggestionsBox}>
                  {suggestedMatches.map((m) => (
                    <button
                      key={m.symbol}
                      type="button"
                      className={styles.suggestionBtn}
                      onClick={() => setSearchQuery(m.symbol)}
                    >
                      <span className={styles.suggestionSym} data-mono>{m.symbol}</span>
                      {m.name && m.name !== m.symbol && (
                        <span className={styles.suggestionName}>{m.name}</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className={styles.searchFieldGroup}>
            <label htmlFor="quarter-selector" className={styles.fieldLabel}>
              Fiscal Quarter:
            </label>
            <select
              id="quarter-selector"
              className={styles.quarterSelect}
              value={selectedQuarter}
              onChange={(e) => setSelectedQuarter(e.target.value)}
            >
              {quarterOptions.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>

          <button
            id="filings-show-button"
            type="button"
            className={styles.showButton}
            onClick={handleShowClick}
            disabled={!searchQuery.trim() || lookupLoading}
          >
            {lookupLoading ? "Loading..." : "Show"}
          </button>
        </div>

        {lookupLoading && (
          <div className={styles.loadingBox} style={{ minHeight: "80px" }}>
            <span className={styles.spinner} />
            <span>Looking up filings data from official archives...</span>
          </div>
        )}
      </section>

      {lookupError && (
        <StatusBanner
          status={lookupStatus}
          message={lookupError}
          type={lookupStatus === 402 || lookupStatus === 403 ? "warn" : "error"}
          error={lookupStatus ? { status: lookupStatus, code: `HTTP_${lookupStatus}`, message: lookupError } : null}
        />
      )}

      {/* Lookup Result Rendering */}
      {lookupResult && (
        <section className={styles.resultSection} data-testid="filings-search-result">
          <div className={styles.companyReport}>
            <div className={styles.companyHeader}>
              <h2>
                {lookupResult.symbol}
                {lookupResult.company && lookupResult.company !== lookupResult.symbol && (
                  <span className={styles.companySubName}> - {lookupResult.company}</span>
                )}
              </h2>
              <span className={styles.periodBadge} data-mono>
                {lookupResult.reporting_period || lookupResult.requested_period}
              </span>
            </div>

            <div className={styles.dataSourceNotice} data-mono style={{ marginBottom: "1rem" }}>
              SOURCE: {lookupResult.source}
            </div>

            {/* Financial Metrics Cards */}
            {lookupResult.verified_metrics && (
              <div className={styles.financialsRow} data-mono>
                {lookupResult.verified_metrics.RevenueFromOperations !== undefined && (
                  <div className={styles.finCard}>
                    <span className={styles.finLabel}>REVENUE (INR CR)</span>
                    <span className={styles.finValue}>{lookupResult.verified_metrics.RevenueFromOperations.toLocaleString()}</span>
                  </div>
                )}
                {lookupResult.verified_metrics.ProfitBeforeTax !== undefined && (
                  <div className={styles.finCard}>
                    <span className={styles.finLabel}>PBT (INR CR)</span>
                    <span className={styles.finValue}>{lookupResult.verified_metrics.ProfitBeforeTax.toLocaleString()}</span>
                  </div>
                )}
                {lookupResult.verified_metrics.ProfitLossForPeriod !== undefined && (
                  <div className={styles.finCard}>
                    <span className={styles.finLabel}>PAT (INR CR)</span>
                    <span className={styles.finValue}>{lookupResult.verified_metrics.ProfitLossForPeriod.toLocaleString()}</span>
                  </div>
                )}
              </div>
            )}

            {/* Rules Table */}
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Entity</th>
                  <th>Fiscal Period</th>
                  <th>Rule ID & Name</th>
                  <th>Claim Quote (Source Text)</th>
                  <th>Filed XBRL Metric</th>
                  <th>Result</th>
                  <th>Deterministic Evidence</th>
                </tr>
              </thead>
              <tbody>
                {lookupResult.rules_evaluated && lookupResult.rules_evaluated.length > 0 ? (
                  lookupResult.rules_evaluated.map((chk, idx) => {
                    const status = String(chk.status || "UNKNOWN").toUpperCase();
                    const statusClass =
                      status === "PASS"
                        ? styles.statusPass
                        : status === "FLAG"
                          ? styles.statusFlag
                          : styles.statusNa;

                    return (
                      <tr key={idx}>
                        <td className={styles.symbolCell} data-mono>{lookupResult.symbol}</td>
                        <td data-mono>{lookupResult.reporting_period || lookupResult.requested_period}</td>
                        <td>
                          <div className={styles.ruleTitle}>
                            <span className={styles.ruleId} data-mono>{chk.rule_id}</span>
                            <span>{RULE_NAMES[chk.rule_id] || chk.rule_name || chk.rule_id}</span>
                          </div>
                        </td>
                        <td className={styles.quoteCell}>
                          <em>&ldquo;{chk.claim_text || "Management stated performance alignment"}&rdquo;</em>
                        </td>
                        <td data-mono className={styles.metricCell}>
                          {chk.metric_name || "--"} = {String(chk.metric_value ?? "--")}
                        </td>
                        <td>
                          <span className={`${styles.statusBadge} ${statusClass}`} data-mono>
                            {status}
                          </span>
                        </td>
                        <td className={styles.evidenceCell}>
                          {chk.evidence_summary || chk.reason || (chk.evidence ? JSON.stringify(chk.evidence) : "--")}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={7} className={styles.emptyCell}>
                      No rule evaluations recorded for this period.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
