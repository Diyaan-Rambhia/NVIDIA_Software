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
  const { isAuthenticated } = useAuth();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<CorrelationScan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);
  const [upgradeTargets, setUpgradeTargets] = useState<string[] | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    let isMounted = true;
    async function loadContagion() {
      setLoading(true);
      setError(null);
      try {
        const scan = await apiFetch<CorrelationScan>("/f1/demo");
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
  }, [isAuthenticated, router]);

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

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>FEATURE 01 / SYSTEMIC CONTAGION</span>
        <h1>Correlation Shifts & Systemic Absorption</h1>
        <p className={styles.lead}>
          Forbes-Rigobon conditional volatility adjustment and systemic absorption ratio tracking across candidate Indian equities.
        </p>
        <div className={styles.dataSourceNotice} data-mono>
          DATA SOURCE: {data?.source_label || "unofficial source, demo only"} | CODE: {data?.code_version || "ae0167c"}
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
        <>
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

          {/* Qualitative Hypotheses & Grounded Evidence */}
          <section className={styles.cardSection}>
            <h2>Formulated Hypotheses & Evidence Citations</h2>
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
                  No qualitative hypotheses triggered by current regime flag.
                </div>
              )}
            </div>
          </section>

          {/* News Pipeline & Parameters Used */}
          <div className={styles.twoColSection}>
            <div className={styles.cardSection}>
              <h3>External News Sentiment Step</h3>
              <p className={styles.cardLead}>
                Contextual pipeline incorporating external macro news feeds.
              </p>
              <div className={styles.statusBox}>
                <span className={styles.statusDot} />
                <strong>Status:</strong> not run: no key
              </div>
              <span className={styles.mutedNote}>
                Macro sentiment step marked unverified until live credentials are provided.
              </span>
            </div>

            <div className={styles.cardSection}>
              <h3>Parameters Used</h3>
              <pre className={styles.paramsBox} data-mono>
                {JSON.stringify(data.parameters_used || {}, null, 2)}
              </pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
