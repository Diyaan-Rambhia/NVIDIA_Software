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
  const [autoDetected, setAutoDetected] = useState(false);
  const [showMapping, setShowMapping] = useState(false);
  const [detectedSummary, setDetectedSummary] = useState<string | null>(null);

  const autoDetectHeaders = async (file: File) => {
    try {
      const slice = file.slice(0, 4096);
      const text = await slice.text();
      const lines = text.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#"));
      if (lines.length === 0) return;

      const headerLine = lines[0];
      const headers = headerLine.split(",").map((h) => h.replace(/^["']|["']$/g, "").trim());

      const patterns: Record<string, RegExp[]> = {
        date: [/^trade_?date$/i, /^order_?date$/i, /^trans(action)?_?date$/i, /^datetime$/i, /^timestamp$/i, /^date$/i, /^time$/i],
        symbol: [/^tradingsymbol$/i, /^symbol$/i, /^ticker$/i, /^scrip$/i, /^stock$/i, /^security$/i, /^instrument$/i, /^asset$/i],
        side: [/^trade_?type$/i, /^transaction_?type$/i, /^action$/i, /^buy[ _/]sell$/i, /^direction$/i, /^side$/i, /^type$/i],
        qty: [/^executed_?qty$/i, /^traded_?qty$/i, /^quantity$/i, /^qty$/i, /^volume$/i, /^shares$/i, /^units$/i],
        price: [/^execution_?price$/i, /^trade_?price$/i, /^avg_?price$/i, /^average_?price$/i, /^unit_?price$/i, /^exec_?price$/i, /^price$/i, /^rate$/i],
        fees: [/^brokerage$/i, /^charges?$/i, /^total_?taxes?$/i, /^fees?$/i, /^commission$/i, /^stt$/i, /^taxes?$/i],
      };

      const matchHeader = (pats: RegExp[], fallbackKeyword?: string) => {
        for (const pat of pats) {
          const found = headers.find((h) => pat.test(h));
          if (found) return found;
        }
        if (fallbackKeyword) {
          const found = headers.find((h) => h.toLowerCase().includes(fallbackKeyword.toLowerCase()));
          if (found) return found;
        }
        return null;
      };

      const mDate = matchHeader(patterns.date, "date");
      const mSymbol = matchHeader(patterns.symbol, "symbol");
      const mSide = matchHeader(patterns.side, "side");
      const mQty = matchHeader(patterns.qty, "qty");
      const mPrice = matchHeader(patterns.price, "price");
      const mFees = matchHeader(patterns.fees, "fee");

      if (mDate) setColDate(mDate);
      if (mSymbol) setColSymbol(mSymbol);
      if (mSide) setColSide(mSide);
      if (mQty) setColQty(mQty);
      if (mPrice) setColPrice(mPrice);
      if (mFees) setColFees(mFees);

      const matchedCount = [mDate, mSymbol, mSide, mQty, mPrice].filter(Boolean).length;
      if (matchedCount >= 1) {
        setAutoDetected(true);
        const parts = [
          mDate ? `Date: ${mDate}` : null,
          mSymbol ? `Symbol: ${mSymbol}` : null,
          mSide ? `Side: ${mSide}` : null,
          mQty ? `Qty: ${mQty}` : null,
          mPrice ? `Price: ${mPrice}` : null,
          mFees ? `Fees: ${mFees}` : null,
        ].filter(Boolean).join(" | ");
        setDetectedSummary(parts);
      }
    } catch {
      // Fallback to defaults
    }
  };

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
          Provide a CSV export from your broker. Column headers and date formats across Indian and international styles are detected automatically.
        </p>

        <div style={{
          padding: "var(--space-3) var(--space-4)",
          backgroundColor: "rgba(255, 255, 255, 0.03)",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "4px",
          fontSize: "13px",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-2)"
        }}>
          <h3 style={{ fontSize: "14px", fontWeight: 600, color: "var(--color-foreground)" }}>Automatic Broker Log Analysis</h3>
          <p style={{ margin: 0, color: "var(--color-muted)" }}>
            Upload any standard CSV export from your broker. Headers for trade date (in any order or format), symbol, side (BUY/SELL), quantity, execution price, and fees are automatically resolved.
          </p>
          <p style={{ margin: 0, color: "var(--color-muted)" }}>
            Optional columns: <code>fees</code>, <code>charges</code>, <code>exchange</code>, <code>segment</code>, <code>marker</code>.
          </p>
        </div>

        <form onSubmit={handleUploadSubmit} className={styles.uploadForm}>
          <div className={styles.fileField}>
            <label htmlFor="csv-file">CSV Trade Log File</label>
            <input
              id="csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setCsvFile(f);
                if (f) {
                  autoDetectHeaders(f);
                }
              }}
              disabled={submitting}
            />
          </div>

          {!autoDetected && (
            <div style={{ marginTop: "calc(-1 * var(--space-2))", marginBottom: "var(--space-2)" }}>
              <button
                type="button"
                onClick={() => setShowMapping(!showMapping)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--color-muted)",
                  cursor: "pointer",
                  fontSize: "12px",
                  textDecoration: "underline",
                }}
              >
                {showMapping ? "Hide column configuration" : "Advanced: Configure column headers manually"}
              </button>
            </div>
          )}

          {autoDetected && (
            <div style={{
              padding: "var(--space-2) var(--space-3)",
              backgroundColor: "rgba(16, 185, 129, 0.08)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              borderRadius: "4px",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-2)",
              color: "var(--color-foreground)"
            }}>
              <span>✓ Auto-detected headers: <strong>{detectedSummary}</strong></span>
              <button
                type="button"
                onClick={() => setShowMapping(!showMapping)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--color-primary, #60a5fa)",
                  cursor: "pointer",
                  textDecoration: "underline",
                  fontSize: "12px",
                  whiteSpace: "nowrap"
                }}
              >
                {showMapping ? "Hide column mapping" : "Customize column mapping"}
              </button>
            </div>
          )}

          {showMapping && (
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
          )}

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
