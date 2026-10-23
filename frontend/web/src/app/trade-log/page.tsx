"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { DecisionReview, F3ReviewRequest } from "@/types/contracts";
import { StatusBanner } from "@/components/StatusBanner";
import { formatINR, formatPercent, formatDecimal } from "@/lib/formatters";
import styles from "./trade-log.module.css";

export default function TradeLogPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked, user, refreshSession } = useAuth();

  const [loadingInitial, setLoadingInitial] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [review, setReview] = useState<DecisionReview | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [statusType, setStatusType] = useState<"ok" | "warn" | "error">("ok");
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  // Form states
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [colDate, setColDate] = useState("trade_date");
  const [colSymbol, setColSymbol] = useState("symbol");
  const [colSide, setColSide] = useState("side");
  const [colQty, setColQty] = useState("quantity");
  const [colPrice, setColPrice] = useState("price");
  const [colFees, setColFees] = useState("fees");
  const [consentGiven, setConsentGiven] = useState(false);

  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push("/login");
      return;
    }
    setLoadingInitial(false);
  }, [isAuthenticated, sessionChecked, router]);

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);

    if (!csvFile) {
      setStatusType("error");
      setStatusMessage("Please select a valid CSV trade execution log file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = async (evt) => {
      const csvText = evt.target?.result as string;
      if (!csvText) {
        setStatusType("error");
        setStatusMessage("Failed to read CSV content.");
        return;
      }

      const payload: F3ReviewRequest = {
        csv_text: csvText,
        mapping: {
          date: colDate.trim(),
          symbol: colSymbol.trim(),
          side: colSide.trim(),
          quantity: colQty.trim(),
          price: colPrice.trim(),
          fees: colFees.trim() || null,
        },
        consent_given: consentGiven,
        benchmark_symbol: "NSEI",
      };

      setSubmitting(true);
      try {
        const result = await apiFetch<DecisionReview>("/f3/review", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        setReview(result);
        setStatusType("ok");
        setStatusMessage("Trade log reviewed and cash flow replay evaluated successfully.");
        await refreshSession();
      } catch (err: unknown) {
        if (err instanceof ApiError) {
          setHttpStatus(err.status);
          const errCode = err.parsed.code || `HTTP_${err.status}`;
          const failing = (err.parsed as any).tickers || (err.parsed as any).failed_symbols || (err.parsed as any).symbol || payload.benchmark_symbol;
          const tickerInfo = failing ? ` (Failing: ${failing})` : "";
          setStatusType("error");
          setStatusMessage(`HTTP ${err.status} [${errCode}]: ${err.parsed.message}${tickerInfo}`);
        } else {
          setStatusType("error");
          setStatusMessage("Execution error auditing trade log.");
        }
      } finally {
        setSubmitting(false);
      }
    };

    reader.readAsText(csvFile);
  };

  const isInstitutional =
    user?.segment === "institutional" || Boolean(user?.plan?.includes("institutional"));

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>FEATURE 03 / FORENSIC TRADE REVIEW</span>
        <h1>Trade Log Audit, XIRR & Benchmark Replay</h1>
        <p className={styles.lead}>
          Ingest execution trade logs, calculate true money-weighted XIRR via Brent solver,
          and replay exact cash flows against Nifty 50 to evaluate behavioral process metrics.
        </p>
      </div>

      {statusMessage && (
        <StatusBanner
          status={httpStatus}
          message={statusMessage}
          type={statusType}
        />
      )}

      {/* CSV Ingestion Form */}
      <section className={styles.uploadSection}>
        <h2>Upload Execution Trade Log</h2>
        <p className={styles.formLead}>
          Provide a CSV export from your broker. Explicitly map your file&apos;s header names to canonical schema fields.
        </p>

        <form onSubmit={handleUploadSubmit} className={styles.uploadForm}>
          <div className={styles.fileField}>
            <label htmlFor="csv-file">CSV Trade Log File</label>
            <input
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              disabled={submitting}
            />
          </div>

          <div className={styles.mappingGrid}>
            <div className={styles.mapField}>
              <label htmlFor="col-date">Date Column Header</label>
              <input
                id="col-date"
                type="text"
                value={colDate}
                onChange={(e) => setColDate(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className={styles.mapField}>
              <label htmlFor="col-symbol">Symbol Column Header</label>
              <input
                id="col-symbol"
                type="text"
                value={colSymbol}
                onChange={(e) => setColSymbol(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className={styles.mapField}>
              <label htmlFor="col-side">Side (Buy/Sell) Header</label>
              <input
                id="col-side"
                type="text"
                value={colSide}
                onChange={(e) => setColSide(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className={styles.mapField}>
              <label htmlFor="col-qty">Quantity Column Header</label>
              <input
                id="col-qty"
                type="text"
                value={colQty}
                onChange={(e) => setColQty(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className={styles.mapField}>
              <label htmlFor="col-price">Execution Price Header</label>
              <input
                id="col-price"
                type="text"
                value={colPrice}
                onChange={(e) => setColPrice(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            <div className={styles.mapField}>
              <label htmlFor="col-fees">Brokerage / Fees Header (Optional)</label>
              <input
                id="col-fees"
                type="text"
                value={colFees}
                onChange={(e) => setColFees(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          <div className={styles.checkboxField}>
            <input
              id="consent-check"
              type="checkbox"
              checked={consentGiven}
              onChange={(e) => setConsentGiven(e.target.checked)}
              disabled={submitting}
            />
            <label htmlFor="consent-check">
              <strong>Consent to persist log:</strong> Store anonymized trade log for historical portfolio tracking (default is OFF: processed purely in memory and destroyed).
            </label>
          </div>

          <button type="submit" className={styles.submitBtn} disabled={submitting}>
            {submitting ? "Analyzing Execution Log..." : "Audit Trade Log"}
          </button>
        </form>
      </section>

      {/* Review Results */}
      {review && (
        <div className={styles.resultsContainer}>
          {/* Process Label Notice */}
          {review.process_metrics?.process_label && (
            <div className={styles.processLabelBox} data-mono>
              PROCESS CLASSIFICATION: {review.process_metrics.process_label}
            </div>
          )}

          {/* Portfolio Aggregates */}
          <section className={styles.cardSection}>
            <h2>Portfolio Aggregation & Return</h2>
            <div className={styles.metricsGrid}>
              <div className={styles.metricCard}>
                <span className={styles.mLabel}>PORTFOLIO XIRR</span>
                <span className={styles.mValue} data-mono>
                  {review.portfolio_xirr !== null ? formatPercent(review.portfolio_xirr, 2) : "NO ROOT"}
                </span>
                <span className={styles.mSub}>Brent root solver (365 day basis)</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>TOTAL COST BASIS</span>
                <span className={styles.mValue} data-mono>
                  {formatINR(review.portfolio?.total_cost)}
                </span>
                <span className={styles.mSub}>Net capital allocated</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>CURRENT MARKET VALUE</span>
                <span className={styles.mValue} data-mono>
                  {formatINR(review.portfolio?.total_market_value)}
                </span>
                <span className={styles.mSub}>As-of terminal evaluation</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>REALIZED P&L</span>
                <span className={styles.mValue} data-mono>
                  {formatINR(review.portfolio?.total_realized_pnl)}
                </span>
                <span className={styles.mSub}>FIFO lot accounting</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>UNREALIZED P&L</span>
                <span className={styles.mValue} data-mono>
                  {formatINR(review.portfolio?.total_unrealized_pnl)}
                </span>
                <span className={styles.mSub}>Open position balance</span>
              </div>
            </div>
          </section>

          {/* Benchmark Replay Table */}
          <section className={styles.cardSection}>
            <h2>Benchmark Cash Flow Replay</h2>
            <p className={styles.cardLead}>
              Simulates investing the identical cash inflows and outflows into benchmark series to isolate trade timing from market beta.
            </p>

            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Benchmark Index</th>
                  <th>Simulated Terminal Value</th>
                  <th>Benchmark XIRR</th>
                  <th>Partial Shortfall Flag</th>
                </tr>
              </thead>
              <tbody>
                {review.benchmark_replays && review.benchmark_replays.length > 0 ? (
                  review.benchmark_replays.map((b, idx) => (
                    <tr key={idx}>
                      <td className={styles.bmNameCell} data-mono>{b.benchmark_name}</td>
                      <td data-mono>{formatINR(b.terminal_value)}</td>
                      <td data-mono>
                        {b.xirr !== null ? formatPercent(b.xirr, 2) : "NO ROOT"}
                      </td>
                      <td>
                        <span
                          className={`${styles.statusBadge} ${
                            b.partial_shortfall ? styles.statusWarn : styles.statusOk
                          }`}
                          data-mono
                        >
                          {b.partial_shortfall ? "YES (SHORTFALL)" : "NO SHORTFALL"}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className={styles.emptyCell}>
                      No benchmark replays computed.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          {/* Behavioral Process Metrics */}
          <section className={styles.cardSection}>
            <h2>Behavioral Process Metrics</h2>
            <div className={styles.metricsGrid}>
              <div className={styles.metricCard}>
                <span className={styles.mLabel}>CONCENTRATION HHI</span>
                <span className={styles.mValue} data-mono>
                  {formatDecimal(review.process_metrics?.concentration_hhi, 4)}
                </span>
                <span className={styles.mSub}>Position weight Herfindahl index</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>PORTFOLIO TURNOVER</span>
                <span className={styles.mValue} data-mono>
                  {formatDecimal(review.process_metrics?.turnover, 4)}
                </span>
                <span className={styles.mSub}>One-way traded volume / average capital</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>MAX DRAWDOWN</span>
                <span className={styles.mValue} data-mono>
                  {formatPercent(review.process_metrics?.max_drawdown, 2)}
                </span>
                <span className={styles.mSub}>Peak-to-trough capital decline</span>
              </div>

              <div className={styles.metricCard}>
                <span className={styles.mLabel}>DISPOSITION EFFECT</span>
                <span className={styles.mValue} data-mono>
                  PGR: {formatDecimal(review.process_metrics?.disposition_effect?.pgr, 2)} / PLR: {formatDecimal(review.process_metrics?.disposition_effect?.plr, 2)}
                </span>
                <span className={styles.mSub}>Odean realized gains vs losses propensity</span>
              </div>
            </div>
          </section>

          {/* Institutional Metrics (if present or institutional tier) */}
          {review.institutional_metrics && (
            <section className={styles.cardSection}>
              <h2>Institutional Risk-Adjusted Metrics</h2>
              <div className={styles.metricsGrid}>
                <div className={styles.metricCard}>
                  <span className={styles.mLabel}>PORTFOLIO BETA</span>
                  <span className={styles.mValue} data-mono>
                    {formatDecimal(review.institutional_metrics.beta, 4)}
                  </span>
                  <span className={styles.mSub}>Sensitivity against Nifty 50</span>
                </div>

                <div className={styles.metricCard}>
                  <span className={styles.mLabel}>JENSEN&apos;S ALPHA</span>
                  <span className={styles.mValue} data-mono>
                    {formatDecimal(review.institutional_metrics.alpha, 4)}
                  </span>
                  <span className={styles.mSub}>Annualized excess return</span>
                </div>

                <div className={styles.metricCard}>
                  <span className={styles.mLabel}>TRACKING ERROR</span>
                  <span className={styles.mValue} data-mono>
                    {formatDecimal(review.institutional_metrics.tracking_error, 4)}
                  </span>
                  <span className={styles.mSub}>Standard deviation of active returns</span>
                </div>

                <div className={styles.metricCard}>
                  <span className={styles.mLabel}>INFORMATION RATIO</span>
                  <span className={styles.mValue} data-mono>
                    {formatDecimal(review.institutional_metrics.information_ratio, 4)}
                  </span>
                  <span className={styles.mSub}>Active return / tracking error</span>
                </div>
              </div>
            </section>
          )}

          {/* Qualitative Review & Disclaimer */}
          <section className={styles.cardSection}>
            <h2>Qualitative Diagnostic Review</h2>
            <div className={styles.reviewText}>{review.review_text}</div>
            <div className={styles.disclaimerBox}>{review.disclaimer}</div>
          </section>

          {/* Parameters Used */}
          <section className={styles.cardSection}>
            <h3>Parameters Used in Review</h3>
            <pre className={styles.paramsBox} data-mono>
              {JSON.stringify(review.parameters_used || {}, null, 2)}
            </pre>
          </section>
        </div>
      )}

      {!review && (
        <section className={styles.cardSection}>
          <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-muted)" }}>
            <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>Upload a trade log</h3>
            <p style={{ fontSize: "0.875rem" }}>
              Select a CSV execution file above and click &ldquo;Audit Trade Log&rdquo; to analyze portfolio XIRR, behavioral biases, and benchmark replay.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
