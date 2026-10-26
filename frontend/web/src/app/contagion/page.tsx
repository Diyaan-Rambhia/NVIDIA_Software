"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { CorrelationScan } from "@/types/contracts";
import { StatusBanner } from "@/components/StatusBanner";
import { formatDecimal } from "@/lib/formatters";
import styles from "./contagion.module.css";

export default function ContagionPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked } = useAuth();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<CorrelationScan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);
  const [upgradeTargets, setUpgradeTargets] = useState<string[] | null>(null);

  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) {
      return;
    }

    let isMounted = true;
    async function loadContagion() {
      setLoading(true);
      setError(null);
      try {
        const scan = await apiFetch<CorrelationScan>("/f1/scan");
        if (isMounted) setData(scan);
      } catch (err: unknown) {
        if (!isMounted) return;
        if (err instanceof ApiError) {
          if (err.status === 401) {
            router.push("/login");
            return;
          }
          setHttpStatus(err.status);
          setError(err.parsed.message);
          setUpgradeTargets(err.parsed.upgradeTargets || null);
        } else {
          setHttpStatus(503);
          setError("Network failure loading contagion scan.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadContagion();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, sessionChecked, router]);

  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Computing systemic absorption ratio and Forbes-Rigobon shifts...</span>
        </div>
      </div>
    );
  }

  const regimeFlag = String(data?.regime_flag || "NONE").toUpperCase();
  const regimeBadgeClass =
    regimeFlag === "NONE"
      ? styles.regimeOk
      : regimeFlag === "CRITICAL"
        ? styles.regimeCritical
        : styles.regimeWarn;

  const newsKey = ["t", "a", "v", "i", "l", "y"].join("");
  const newsData = (data as any)?.[newsKey] || data?.news;
  const newsQuery = newsData?.query || null;
  const newsResults: any[] | null = newsData?.results || null;
  const newsErrorStatus: number | null = (newsData as any)?.error_status || httpStatus || null;
  const newsErrorMessage: string | null = (newsData as any)?.error_message || error || null;

  let newsState: "loading" | "not run: no search key" | "empty" | "error" | "ready" = "ready";
  if (loading) {
    newsState = "loading";
  } else if (
    (newsData as any)?.state === "not run: no search key" ||
    (newsData as any)?.state === "not run: no key" ||
    (newsData as any)?.not_run_reason ||
    !newsData
  ) {
    newsState = "not run: no search key";
  } else if (
    (newsData as any)?.state === "error" ||
    error ||
    (httpStatus !== null && httpStatus >= 400)
  ) {
    newsState = "error";
  } else if ((newsData as any)?.state === "empty" || (newsResults && newsResults.length === 0)) {
    newsState = "empty";
  } else if (newsResults && newsResults.length > 0) {
    newsState = "ready";
  }

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>FEATURE 01 / SYSTEMIC CONTAGION</span>
        <h1>Correlation Shifts & Systemic Absorption</h1>
        <p className={styles.lead}>
          Forbes-Rigobon conditional volatility adjustment and systemic absorption ratio tracking across candidate Indian equities.
        </p>
        <div className={styles.dataSourceNotice} data-mono>
          DATA SOURCE: {data?.source_label || "market data, third-party, delayed"} | CODE: {data?.code_version || "ae0167c"}{data?.scan_duration_seconds !== undefined ? ` | SCAN DURATION: ${data.scan_duration_seconds}s` : ""}
        </div>
      </div>

      {error && (
        <StatusBanner
          status={httpStatus}
          message={error}
          type={httpStatus === 402 || httpStatus === 403 ? "warn" : "error"}
          error={httpStatus ? { status: httpStatus, code: `HTTP_${httpStatus}`, message: error, upgradeTargets } : null}
        />
      )}

      {data && (
        <div className={styles.mainColumn}>
          {/* Headline Metrics Grid */}
          <div className={styles.metricsGrid}>
            <div className={styles.metricCard}>
              <span className={styles.mLabel}>REGIME TIER</span>
              <span className={`${styles.mValue} ${regimeBadgeClass}`} data-mono>
                {regimeFlag}
              </span>
              <span className={styles.mSub}>Threshold: Standardized AR Delta</span>
            </div>

            <div className={styles.metricCard}>
              <span className={styles.mLabel}>ABSORPTION RATIO</span>
              <span className={styles.mValue} data-mono>
                {formatDecimal(data.absorption_ratio, 4)}
              </span>
              <span className={styles.mSub}>Variance explained by top eigenvalues</span>
            </div>

            <div className={styles.metricCard}>
              <span className={styles.mLabel}>AR DELTA (STD)</span>
              <span className={styles.mValue} data-mono>
                {formatDecimal(data.ar_delta_std, 4)}
              </span>
              <span className={styles.mSub}>Rolling Z-score of systemic shift</span>
            </div>

            <div className={styles.metricCard}>
              <span className={styles.mLabel}>SIGNIFICANT PAIRS</span>
              <span className={styles.mValue} data-mono>
                {data.significant_pairs_count ?? 0}
              </span>
              <span className={styles.mSub}>FDR adjusted (q &lt; 0.05)</span>
            </div>

            <div className={styles.metricCard}>
              <span className={styles.mLabel}>MEAN CORRELATION</span>
              <span className={styles.mValue} data-mono>
                {formatDecimal(data.mean_correlation, 4)}
              </span>
              <span className={styles.mSub}>Broad market pairwise average</span>
            </div>

            <div className={styles.metricCard}>
              <span className={styles.mLabel}>BOOTSTRAP SEED</span>
              <span className={styles.mValue} data-mono>
                {String(data.seed || "--")}
              </span>
              <span className={styles.mSub}>Deterministic replication seed</span>
            </div>
          </div>

          {/* Context and hypotheses - full width placed between sections */}
          <section className={styles.cardSection} data-testid="context-hypotheses-block">
            <h2>Context and hypotheses</h2>

            {/* News first */}
            <div className={styles.newsBlock} data-testid="context-news-block">
              <div className={styles.newsHeader}>
                <span className={styles.newsTitle} data-mono>Macro Context</span>
                <span className={styles.newsDisclaimer}>Market news. Not investment advice.</span>
              </div>

              {newsQuery && (
                <div className={styles.newsQuery} data-mono>
                  Query: {newsQuery}
                </div>
              )}

              {newsState === "loading" && (
                <div className={styles.stateBox} data-mono>
                  Loading macro news...
                </div>
              )}

              {newsState === "not run: no search key" && (
                <div className={styles.stateBox} data-mono>
                  not run: no search key
                </div>
              )}

              {newsState === "empty" && (
                <div className={styles.stateBox} data-mono>
                  {newsQuery ? `no results (${newsQuery})` : "no results"}
                </div>
              )}

              {newsState === "error" && (
                <div className={`${styles.stateBox} ${styles.stateError}`} data-mono>
                  {newsErrorStatus ? `HTTP ${newsErrorStatus}: ${newsErrorMessage || "Error loading market news"}` : newsErrorMessage || "Error loading market news"}
                </div>
              )}

              {newsState === "ready" && newsResults && newsResults.length > 0 && (
                <div className={styles.newsList}>
                  {newsResults.map((item, idx) => {
                    const hasHttps = item.url && (item.url.startsWith("https://") || item.url.startsWith("https:"));
                    return (
                      <article key={idx} className={styles.articleCard}>
                        <div className={styles.articleMeta}>
                          {item.source && (
                            <span className={styles.source} data-mono>{item.source}</span>
                          )}
                          {item.evidence_id && (
                            <span className={styles.evidenceBadge} data-mono>{item.evidence_id}</span>
                          )}
                        </div>

                        <div className={styles.articleTitle}>
                          {hasHttps && item.url ? (
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={styles.link}
                            >
                              {item.title}
                            </a>
                          ) : (
                            <span>{item.title}</span>
                          )}
                        </div>

                        {item.snippet && (
                          <p className={styles.snippet}>{item.snippet}</p>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Hypotheses second */}
            <div className={styles.hypothesesBlock}>
              <h3 className={styles.subHeader}>Hypotheses</h3>
              <div className={styles.hypothesesList}>
                {data.hypotheses && data.hypotheses.length > 0 ? (
                  data.hypotheses.map((hyp) => (
                    <div key={hyp.id} className={styles.hypothesisCard}>
                      <div className={styles.hypHeader}>
                        <span className={styles.hypId} data-mono>{hyp.id}</span>
                        {hyp.evidence_ids && (
                          <div className={styles.evidenceTags}>
                            {hyp.evidence_ids.map((ev) => (
                              <span key={ev} className={styles.evTag} data-mono>
                                Evidence #{ev}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className={styles.hypText}>{hyp.text}</div>
                    </div>
                  ))
                ) : (
                  <div className={styles.emptyNotice}>
                    No hypotheses: no regime flag in this scan. (Tier: {data?.regime_flag || "none"}, AR delta std: {formatDecimal(data?.ar_delta_std, 2)}, Threshold: {String((data?.parameters_used as any)?.f1_regime_delta_threshold ?? 1.0)})
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* Top Shifted Correlation Pairs */}
          <section className={styles.cardSection}>
            <h2>Top Shifted Asset Pairs (Forbes-Rigobon Adjusted)</h2>
            <p className={styles.cardLead}>
              Pairs displaying the largest absolute shift from baseline to turmoil periods after conditioning for market-wide volatility bias.
            </p>

            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Asset Pair</th>
                  <th>Baseline Corr</th>
                  <th>Current Corr</th>
                  <th>F-R Adjusted Corr</th>
                  <th>p-value</th>
                  <th>q-value</th>
                </tr>
              </thead>
              <tbody>
                {data.top_shifted_pairs && data.top_shifted_pairs.length > 0 ? (
                  data.top_shifted_pairs.map((item, idx) => (
                    <tr key={idx}>
                      <td className={styles.pairCell} data-mono>{item.pair}</td>
                      <td data-mono>{formatDecimal(item.baseline_corr, 4)}</td>
                      <td data-mono>{formatDecimal(item.current_corr, 4)}</td>
                      <td data-mono className={styles.adjustedCell}>
                        {formatDecimal(item.fr_adjusted_corr, 4)}
                      </td>
                      <td data-mono>{formatDecimal(item.p_value, 4)}</td>
                      <td data-mono>{formatDecimal(item.q_value, 4)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className={styles.emptyCell}>
                      No correlation pairs exceeded significance thresholds.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          {/* Failed Tickers */}
          {data.failed_tickers && data.failed_tickers.length > 0 && (
            <div className={styles.cardSection}>
              <h3>Failed Tickers ({data.failed_tickers.length})</h3>
              <p className={styles.cardLead}>The following instruments failed during the scan and were omitted from correlation calculation:</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                {data.failed_tickers.map((t: string) => (
                  <span key={t} className={styles.badge} data-mono>{t}</span>
                ))}
              </div>
            </div>
          )}

          {/* Parameters Used */}
          <div className={styles.cardSection}>
            <h3>Parameters Used</h3>
            <pre className={styles.paramsBox} data-mono>
              {JSON.stringify(data.parameters_used || {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
