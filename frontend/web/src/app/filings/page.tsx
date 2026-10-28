"use client";

import React, { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { StatusBanner } from "@/components/StatusBanner";
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
  claim_quote?: string | null;
  metric_name?: string;
  metric_value?: string | number;
  metric_unit?: string;
  evidence_summary?: string;
  period?: string;
  source_url?: string | null;
}

interface TranscriptHighlight {
  category: string;
  quote: string;
}

interface TranscriptInfo {
  source_type?: string;
  source_url?: string | null;
  pdf_url?: string | null;
  word_count?: number;
  extraction_method?: string;
  retrieved_at?: string;
  validation_status?: string;
  local_path?: string;
  highlights?: TranscriptHighlight[];
  report?: any;
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
  transcript_info?: TranscriptInfo | null;
}

interface MissingQuarterInfo {
  company: string;
  period: string;
  availablePeriods: string[];
}

const RULE_NAMES: Record<string, string> = {
  R0: "Exact Verbatim Quote Check",
  R1: "Revenue Consistency",
  R2: "Growth Magnitude Verification",
  R3: "Growth Trend & Momentum Verification",
  R4: "Profitability & Margin Discipline",
  R5: "Operating Cash Flow Quality",
  R6: "Working Capital & Receivables Discipline",
  R7: "Understatement & Commentary Asymmetry",
};

const FILINGS_FIRST_FISCAL_YEAR = 2001; // label FY01

const QUARTER_BUTTONS = [
  { num: 1, label: "Q1", months: "Apr–Jun" },
  { num: 2, label: "Q2", months: "Jul–Sep" },
  { num: 3, label: "Q3", months: "Oct–Dec" },
  { num: 4, label: "Q4", months: "Jan–Mar" },
];

function getFiscalCalendarInfo(nowDate = new Date()) {
  const month = nowDate.getMonth();
  const fullYear = nowDate.getFullYear();
  let currentFiscalYear: number;
  let currentQuarter: number;

  if (month >= 3) {
    currentFiscalYear = fullYear + 1;
    if (month <= 5) currentQuarter = 1;
    else if (month <= 8) currentQuarter = 2;
    else currentQuarter = 3;
  } else {
    currentFiscalYear = fullYear;
    currentQuarter = 4;
  }

  const years: { year: number; label: string }[] = [];
  for (let y = currentFiscalYear; y >= FILINGS_FIRST_FISCAL_YEAR; y--) {
    const short = String(y % 100).padStart(2, "0");
    years.push({ year: y, label: `FY${short}` });
  }

  return { currentFiscalYear, currentQuarter, years };
}

export default function FilingsPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked } = useAuth();

  // Calendar info computed from system clock
  const { currentFiscalYear, currentQuarter, years: fiscalYearOptions } = useMemo(
    () => getFiscalCalendarInfo(),
    []
  );

  // Top 50 State
  const [top50, setTop50] = useState<CompanySuggestion[]>([]);
  const [top50Loading, setTop50Loading] = useState(true);
  const [top50Error, setTop50Error] = useState<string | null>(null);

  // Search & Autocomplete State
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<CompanySuggestion[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [isPickerOpen, setIsPickerOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Quarter Selection State
  const [selectedFiscalYear, setSelectedFiscalYear] = useState<number>(currentFiscalYear);
  const defaultQuarterLabel = `Q${currentQuarter} FY${String(currentFiscalYear % 100).padStart(2, "0")}`;
  const [selectedQuarter, setSelectedQuarter] = useState<string>(defaultQuarterLabel);

  // Lookup execution state
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupResult, setLookupResult] = useState<LookupResult | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [lookupStatus, setLookupStatus] = useState<number | null>(null);
  const [missingQuarterInfo, setMissingQuarterInfo] = useState<MissingQuarterInfo | null>(null);
  const [customText, setCustomText] = useState("");
  const [showCustomBox, setShowCustomBox] = useState(false);

  const routerRef = useRef(router);
  routerRef.current = router;

  // Load Nifty 50 on mount
  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      routerRef.current.push("/login");
      return;
    }
    if (!isAuthenticated) return;

    let isMounted = true;
    async function loadTop50() {
      setTop50Loading(true);
      setTop50Error(null);
      try {
        const list = await apiFetch<CompanySuggestion[]>("/f2/top50");
        if (isMounted) {
          setTop50(Array.isArray(list) ? list : []);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        if (err instanceof ApiError) {
          if (err.status === 401) {
            routerRef.current.push("/login");
            return;
          }
          setTop50Error(err.parsed.message || `Failed to load Nifty 50 (HTTP ${err.status})`);
        } else {
          setTop50Error("Failed to connect to backend for Nifty 50 constituents.");
        }
        setTop50([]);
      } finally {
        if (isMounted) setTop50Loading(false);
      }
    }

    loadTop50();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, sessionChecked]);

  // Debounced search on server as user types
  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }

    setSearchLoading(true);
    const timer = setTimeout(async () => {
      try {
        const results = await apiFetch<CompanySuggestion[]>(
          `/f2/search?q=${encodeURIComponent(q)}`
        );
        setSearchResults(Array.isArray(results) ? results : []);
      } catch (err) {
        setSearchResults([]);
      } finally {
        setSearchLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Close picker on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        pickerRef.current &&
        !pickerRef.current.contains(e.target as Node) &&
        searchInputRef.current &&
        !searchInputRef.current.contains(e.target as Node)
      ) {
        setIsPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleYearChange = useCallback(
    (newYear: number) => {
      setSelectedFiscalYear(newYear);
      // If currently selected quarter is a Q{1-4} label, update its year
      if (selectedQuarter.startsWith("Q")) {
        const qNum = selectedQuarter.slice(0, 2);
        const short = String(newYear % 100).padStart(2, "0");
        const nextLabel = `${qNum} FY${short}`;
        setSelectedQuarter(nextLabel);
      }
    },
    [selectedQuarter]
  );

  const isQuarterDisabled = useCallback(
    (fy: number, qNum: number) => {
      if (fy > currentFiscalYear) return true;
      if (fy === currentFiscalYear && qNum > currentQuarter) return true;
      return false;
    },
    [currentFiscalYear, currentQuarter]
  );

  const handleSelectCompany = (sym: string) => {
    setSearchQuery(sym);
    setIsPickerOpen(false);
  };

  const handleShowClick = async () => {
    const comp = searchQuery.trim();
    if (!comp) return;

    setLookupLoading(true);
    setLookupError(null);
    setLookupStatus(null);
    setLookupResult(null);
    setMissingQuarterInfo(null);

    const periodParam = selectedQuarter.trim() || "Annual";

    try {
      let url = `/f2/lookup?company=${encodeURIComponent(comp)}&period=${encodeURIComponent(periodParam)}`;
      if (customText.trim()) {
        url += `&custom_text=${encodeURIComponent(customText.trim())}`;
      }
      const res = await apiFetch<LookupResult>(url);
      setLookupResult(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          routerRef.current.push("/login");
          return;
        }
        setLookupStatus(err.status);
        if (err.status === 404 && (err.parsed.code === "period_not_found" || err.parsed.message?.includes("no data for") || err.parsed.message?.includes("No data for"))) {
          setMissingQuarterInfo({
            company: comp,
            period: periodParam,
            availablePeriods: Array.isArray((err.parsed as any).available_periods)
              ? (err.parsed as any).available_periods
              : [],
          });
        } else {
          setLookupError(err.parsed.message || `Lookup failed with HTTP ${err.status}`);
        }
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

      {top50Error && (
        <StatusBanner
          status={502}
          message={`Error loading Nifty 50: ${top50Error}`}
          type="error"
        />
      )}

      {/* Top Search & Filter Section */}
      <section className={styles.searchSection} aria-label="Company Search">
        <div className={styles.searchControlsRow}>
          {/* Company Search Field */}
          <div className={styles.searchFieldGroup}>
            <label htmlFor="company-search-input" className={styles.fieldLabel}>
              Find Company:
            </label>
            <div className={styles.inputWithSuggestions}>
              <input
                id="company-search-input"
                ref={searchInputRef}
                type="text"
                className={styles.searchInput}
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setIsPickerOpen(true);
                }}
                onFocus={() => setIsPickerOpen(true)}
                placeholder="Type company symbol or name..."
                autoComplete="off"
              />

              {isPickerOpen && (
                <div ref={pickerRef} className={styles.suggestionsBox} data-testid="company-picker-dropdown">
                  {searchQuery.trim().length >= 2 ? (
                    <>
                      <div className={styles.pickerGroupHeader}>Search Results</div>
                      {searchLoading ? (
                        <div className={styles.suggestionBtn} style={{ color: "var(--color-muted)" }}>
                          Searching official equity list...
                        </div>
                      ) : searchResults.length > 0 ? (
                        searchResults.map((m) => (
                          <button
                            key={m.symbol}
                            type="button"
                            className={styles.suggestionBtn}
                            onClick={() => handleSelectCompany(m.symbol)}
                          >
                            <span className={styles.suggestionSym} data-mono>{m.symbol}</span>
                            {m.name && m.name !== m.symbol && (
                              <span className={styles.suggestionName}>{m.name}</span>
                            )}
                          </button>
                        ))
                      ) : (
                        <div className={styles.suggestionBtn} style={{ color: "var(--color-muted)" }}>
                          No matching companies found.
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className={styles.pickerGroupHeader}>Nifty 50</div>
                      {top50Loading ? (
                        <div className={styles.suggestionBtn} style={{ color: "var(--color-muted)" }}>
                          Loading Nifty 50 constituents...
                        </div>
                      ) : top50.length > 0 ? (
                        top50.map((m) => (
                          <button
                            key={m.symbol}
                            type="button"
                            className={styles.suggestionBtn}
                            onClick={() => handleSelectCompany(m.symbol)}
                          >
                            <span className={styles.suggestionSym} data-mono>{m.symbol}</span>
                            {m.name && m.name !== m.symbol && (
                              <span className={styles.suggestionName}>{m.name}</span>
                            )}
                          </button>
                        ))
                      ) : (
                        <div className={styles.suggestionBtn} style={{ color: "var(--color-muted)" }}>
                          Nifty 50 list unavailable.
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Calendar-Style Quarter Selector */}
          <div className={styles.searchFieldGroup} style={{ flex: 2, minWidth: "320px" }}>
            <div className={styles.calendarPickerContainer} data-testid="fiscal-calendar-picker">
              <div className={styles.pickerYearRow}>
                <label htmlFor="fiscal-year-select" className={styles.fieldLabel}>
                  Fiscal Year:
                </label>
                <select
                  id="fiscal-year-select"
                  className={styles.yearSelect}
                  value={selectedFiscalYear}
                  onChange={(e) => handleYearChange(Number(e.target.value))}
                >
                  {fiscalYearOptions.map((fy) => (
                    <option key={fy.year} value={fy.year}>
                      {fy.label} ({fy.year})
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.pickerQuarterRow} role="group" aria-label="Fiscal Quarter Buttons">
                {QUARTER_BUTTONS.map((q) => {
                  const label = `Q${q.num} FY${String(selectedFiscalYear % 100).padStart(2, "0")}`;
                  const isSelected = selectedQuarter === label;
                  const isDisabled = isQuarterDisabled(selectedFiscalYear, q.num);
                  return (
                    <button
                      key={q.num}
                      type="button"
                      className={`${styles.quarterBtn} ${isSelected ? styles.quarterBtnActive : ""}`}
                      disabled={isDisabled}
                      onClick={() => setSelectedQuarter(label)}
                      title={isDisabled ? "Future quarter not yet completed" : label}
                    >
                      <span className={styles.quarterBtnNum}>Q{q.num}</span>
                      <span className={styles.quarterBtnMonths}>{q.months}</span>
                    </button>
                  );
                })}
                <button
                  type="button"
                  className={`${styles.quarterBtn} ${styles.annualBtn} ${selectedQuarter === "Annual" ? styles.quarterBtnActive : ""}`}
                  disabled={selectedFiscalYear > currentFiscalYear}
                  onClick={() => setSelectedQuarter("Annual")}
                >
                  <span className={styles.quarterBtnNum}>Annual</span>
                  <span className={styles.quarterBtnMonths}>Full FY</span>
                </button>
              </div>
            </div>
          </div>

          {/* Action Button */}
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

        {/* Optional Custom Management Announcement / Press Release Input */}
        <div className={styles.customCommentaryBox}>
          <button
            type="button"
            className={styles.customCommentaryToggle}
            onClick={() => setShowCustomBox(!showCustomBox)}
          >
            {showCustomBox ? "▲ Hide Custom Commentary Input" : "▼ Audit Custom Press Release / Earnings Concall Snippet (Optional)"}
          </button>
          {showCustomBox && (
            <textarea
              className={styles.customTextarea}
              placeholder="Paste management announcement, CEO guidance statement, or earnings call transcript text to audit verbatim against official filed metrics..."
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              rows={3}
            />
          )}
        </div>

        {lookupLoading && (
          <div className={styles.loadingBox} style={{ minHeight: "80px", marginTop: "1rem" }}>
            <span className={styles.spinner} />
            <span>Looking up filings data from official archives...</span>
          </div>
        )}
      </section>

      {/* Missing Quarter Notice (Item 5) */}
      {missingQuarterInfo && (
        <div className={styles.missingQuarterBox} data-testid="missing-quarter-notice">
          <div className={styles.missingQuarterTitle}>
            No data for {missingQuarterInfo.company} in {missingQuarterInfo.period}.
          </div>
          <p className={styles.missingQuarterNote}>
            The source may not hold machine-readable results for older quarters.
          </p>
          {missingQuarterInfo.availablePeriods && missingQuarterInfo.availablePeriods.length > 0 && (
            <div className={styles.availablePeriodsList}>
              Available quarters for this company: <strong>{missingQuarterInfo.availablePeriods.join(", ")}</strong>
            </div>
          )}
        </div>
      )}

      {/* General Lookup Error */}
      {lookupError && !missingQuarterInfo && (
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

            {/* Transcript & Commentary Source Card */}
            {lookupResult.transcript_info && (
              <div
                className={styles.transcriptCard}
                data-testid="transcript-info-card"
              >
                <div className={styles.transcriptHeader}>
                  <div className={styles.transcriptBadgeRow}>
                    <span
                      className={`${styles.transcriptBadge} ${
                        lookupResult.transcript_info.source_type === "official_ir" ||
                        lookupResult.transcript_info.source_type === "official_bse" ||
                        lookupResult.transcript_info.source_type === "official_nse"
                          ? styles.badgeOfficial
                          : lookupResult.transcript_info.source_type === "custom_user_text"
                            ? styles.badgeCustom
                            : styles.badgeAggregator
                      }`}
                      data-mono
                    >
                      {lookupResult.transcript_info.source_type === "official_ir" && "OFFICIAL IR CONCALL TRANSCRIPT"}
                      {lookupResult.transcript_info.source_type === "official_bse" && "OFFICIAL BSE FILING TRANSCRIPT"}
                      {lookupResult.transcript_info.source_type === "official_nse" && "OFFICIAL NSE FILING TRANSCRIPT"}
                      {lookupResult.transcript_info.source_type === "aggregator" && "AGGREGATOR CONCALL TRANSCRIPT"}
                      {lookupResult.transcript_info.source_type === "custom_user_text" && "CUSTOM MANAGEMENT COMMENTARY"}
                      {lookupResult.transcript_info.source_type === "not_found" && "CONCALL NOT YET ARCHIVED"}
                    </span>
                    {lookupResult.transcript_info.validation_status === "passed" && (
                      <span className={styles.transcriptValidationBadge} data-mono>
                        VERIFIED AUDIT SOURCE
                      </span>
                    )}
                  </div>
                  {(lookupResult.transcript_info.pdf_url || (lookupResult.transcript_info.source_url && lookupResult.transcript_info.source_url.startsWith("http"))) && (
                    <a
                      href={lookupResult.transcript_info.pdf_url || lookupResult.transcript_info.source_url || "#"}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.transcriptPdfBtn}
                    >
                      View Original Document ↗
                    </a>
                  )}
                </div>

                <div className={styles.transcriptDetails} data-mono>
                  {lookupResult.transcript_info.word_count !== undefined && lookupResult.transcript_info.word_count > 0 && (
                    <span className={styles.transcriptDetailItem}>
                      <strong>Length:</strong> {lookupResult.transcript_info.word_count.toLocaleString()} words
                    </span>
                  )}
                  {lookupResult.transcript_info.extraction_method && (
                    <span className={styles.transcriptDetailItem}>
                      <strong>Method:</strong> {lookupResult.transcript_info.extraction_method}
                    </span>
                  )}
                  {lookupResult.transcript_info.source_url && (
                    <span className={styles.transcriptDetailItem}>
                      <strong>Source:</strong>{" "}
                      {(() => {
                        try {
                          return new URL(lookupResult.transcript_info.source_url || "").hostname;
                        } catch {
                          return lookupResult.transcript_info.source_url;
                        }
                      })()}
                    </span>
                  )}
                </div>

                {/* Executive Concall Highlights */}
                {lookupResult.transcript_info.highlights && lookupResult.transcript_info.highlights.length > 0 && (
                  <div className={styles.highlightsContainer} data-testid="transcript-highlights">
                    <div className={styles.highlightsTitle}>Executive Call Highlights & Disclosures</div>
                    <div className={styles.highlightsGrid}>
                      {lookupResult.transcript_info.highlights.map((hl, hIdx) => (
                        <div key={hIdx} className={styles.highlightItem}>
                          <span className={styles.highlightCategory} data-mono>{hl.category}</span>
                          <span className={styles.highlightQuote}>&ldquo;{hl.quote}&rdquo;</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {lookupResult.transcript_info.source_type === "not_found" && (
                  <p className={styles.transcriptNotFoundNote}>
                    No official conference call transcript has been retrieved for {lookupResult.symbol} ({lookupResult.reporting_period || lookupResult.requested_period}) yet. You can paste custom management commentary below to audit specific quotes.
                  </p>
                )}
              </div>
            )}

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
                            <span>{chk.rule_name || RULE_NAMES[chk.rule_id] || chk.rule_id}</span>
                          </div>
                        </td>
                        <td className={styles.quoteCell}>
                          {chk.claim_quote || chk.claim_text ? (
                            <>
                              <em>&ldquo;{chk.claim_quote || chk.claim_text}&rdquo;</em>
                              {chk.source_url && (
                                <a
                                  href={chk.source_url.startsWith("http") ? chk.source_url : undefined}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className={styles.sourceLink}
                                >
                                  {chk.source_url.startsWith("http") ? "↗ View Source Document" : chk.source_url}
                                </a>
                              )}
                            </>
                          ) : (
                            <span style={{ color: "var(--color-muted)", fontStyle: "italic" }}>
                              No management claim text for this period.
                            </span>
                          )}
                        </td>
                        <td data-mono className={styles.metricCell}>
                          {chk.metric_name ? (
                            chk.metric_value !== null && chk.metric_value !== undefined ? (
                              `${chk.metric_name}: ${typeof chk.metric_value === "number" ? chk.metric_value.toLocaleString("en-IN") : chk.metric_value} ${chk.metric_unit || "INR Cr"} (${chk.period || lookupResult.reporting_period || lookupResult.requested_period || "Annual"})`
                            ) : (
                              `${chk.metric_name} (${chk.period || "Annual"})`
                            )
                          ) : (
                            "N/A"
                          )}
                        </td>
                        <td>
                          <span className={`${styles.statusBadge} ${statusClass}`} data-mono>
                            {status.toLowerCase()}
                          </span>
                        </td>
                        <td className={styles.evidenceCell}>
                          {chk.reason || chk.evidence_summary || (chk.evidence ? JSON.stringify(chk.evidence) : "--")}
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
