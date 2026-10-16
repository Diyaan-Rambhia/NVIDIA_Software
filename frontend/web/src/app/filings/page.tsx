"use client";

import React, { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { FilingsDemo, FilingCheck } from "@/types/contracts";
import { StatusBanner } from "@/components/StatusBanner";
import styles from "./filings.module.css";

export default function FilingsPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<FilingsDemo | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string>("ALL");
  const [selectedRule, setSelectedRule] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    let isMounted = true;
    async function loadFilings() {
      setLoading(true);
      setError(null);
      try {
        const demo = await apiFetch<FilingsDemo>("/f2/demo");
        if (isMounted) setData(demo);
      } catch (err: unknown) {
        if (!isMounted) return;
        if (err instanceof ApiError) {
          if (err.status === 401) {
            router.push("/login");
            return;
          }
          setHttpStatus(err.status);
          setError(err.parsed.message);
        } else {
          setHttpStatus(503);
          setError("Network failure loading filings audit.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadFilings();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, router]);

  // Unique companies list for the picker
  const companies = useMemo(() => {
    if (!data?.companies_audited) return [];
    return data.companies_audited.map((c) => c.symbol);
  }, [data]);

  // Filtered checks
  const filteredChecks = useMemo(() => {
    if (!data?.checks) return [];
    return data.checks.filter((chk) => {
      const matchCompany = selectedCompany === "ALL" || chk.symbol === selectedCompany;
      const matchRule = selectedRule === "ALL" || chk.rule_id === selectedRule;
      return matchCompany && matchRule;
    });
  }, [data, selectedCompany, selectedRule]);

  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Parsing XBRL statements and evaluating rules R0 through R7...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>FEATURE 02 / FILINGS CONSISTENCY</span>
        <h1>XBRL Statements & Verbatim Quote Verification</h1>
        <p className={styles.lead}>
          Deterministic audit comparing management press releases and earnings transcripts against filed Ind AS XBRL financials.
        </p>
        <div className={styles.limitsCallout}>
          <strong>Statutory Scope Notice:</strong> Revenue and profit checks only. Balance sheet line items and non-financial disclosures require manual verification.
        </div>
      </div>

      {error && (
        <StatusBanner
          status={httpStatus}
          message={error}
          type={httpStatus === 402 ? "upgrade" : "error"}
          error={httpStatus ? { status: httpStatus, code: `HTTP_${httpStatus}`, message: error } : null}
        />
      )}

      {data && (
        <>
          {/* Companies Ingestion Summary */}
          <section className={styles.summarySection}>
            <div className={styles.summaryHeader}>
              <h2>Audited Companies</h2>
              <span className={styles.verifierStatus} data-mono>
                VERIFIER STATUS: {data.verifier_status || "DETERMINISTIC VERIFICATION ACTIVE"}
              </span>
            </div>

            <div className={styles.companyPills}>
              <button
                type="button"
                className={`${styles.companyPill} ${selectedCompany === "ALL" ? styles.pillActive : ""}`}
                onClick={() => setSelectedCompany("ALL")}
              >
                ALL AUDITED ({data.companies_audited?.length ?? 0})
              </button>
              {companies.map((sym) => (
                <button
                  key={sym}
                  type="button"
                  className={`${styles.companyPill} ${selectedCompany === sym ? styles.pillActive : ""}`}
                  onClick={() => setSelectedCompany(sym)}
                >
                  {sym}
                </button>
              ))}
            </div>
          </section>

          {/* Rules R0-R7 Audit Checks Table */}
          <section className={styles.tableSection}>
            <div className={styles.tableControls}>
              <h2>Rule Evaluations (R0 through R7)</h2>
              <div className={styles.filterRow}>
                <label htmlFor="rule-filter" className={styles.filterLabel}>Filter by Rule:</label>
                <select
                  id="rule-filter"
                  className={styles.ruleSelect}
                  value={selectedRule}
                  onChange={(e) => setSelectedRule(e.target.value)}
                >
                  <option value="ALL">All Rules (R0 to R7)</option>
                  <option value="R0">R0: Exact Verbatim Quote Check</option>
                  <option value="R1">R1: Revenue Consistency</option>
                  <option value="R2">R2: Operating Margin Alignment</option>
                  <option value="R3">R3: PAT Growth vs Statement</option>
                  <option value="R4">R4: YoY Trend Inconsistency</option>
                  <option value="R5">R5: Standalone vs Consolidated Mismatch</option>
                  <option value="R6">R6: Unit & Scale Shift</option>
                  <option value="R7">R7: Sector Relative Performance Flag</option>
                </select>
              </div>
            </div>

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
                {filteredChecks.length > 0 ? (
                  filteredChecks.map((chk: FilingCheck, idx: number) => {
                    const statusClass =
                      chk.status === "PASS"
                        ? styles.statusPass
                        : chk.status === "FLAG"
                        ? styles.statusFlag
                        : styles.statusNa;

                    return (
                      <tr key={idx}>
                        <td className={styles.symbolCell} data-mono>{chk.symbol}</td>
                        <td data-mono>{chk.period}</td>
                        <td>
                          <div className={styles.ruleTitle}>
                            <span className={styles.ruleId} data-mono>{chk.rule_id}</span>
                            <span>{chk.rule_name}</span>
                          </div>
                        </td>
                        <td className={styles.quoteCell}>
                          <em>&ldquo;{chk.claim_text}&rdquo;</em>
                        </td>
                        <td data-mono className={styles.metricCell}>
                          {chk.metric_name} = {chk.metric_value}
                        </td>
                        <td>
                          <span className={`${styles.statusBadge} ${statusClass}`} data-mono>
                            {chk.status}
                          </span>
                        </td>
                        <td className={styles.evidenceCell}>
                          {chk.evidence_summary || chk.rationale || "--"}
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={7} className={styles.emptyCell}>
                      No rules matched the selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
