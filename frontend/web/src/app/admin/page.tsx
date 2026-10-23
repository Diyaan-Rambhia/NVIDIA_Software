"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import {
  OpsStatus,
  OpsConfig,
  OpsParameters,
  OpsEvent,
  OpsLlmRow,
} from "@/types/agent";
import { VerificationResponse } from "@/types/api";
import { StatusBanner } from "@/components/StatusBanner";
import { formatDecimal } from "@/lib/formatters";
import styles from "./admin.module.css";

export default function AdminPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked, isAdmin } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  // Operational state
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null);
  const [readyStatus, setReadyStatus] = useState<{ ready: boolean; checks: Record<string, unknown> } | null>(null);
  const [healthStatus, setHealthStatus] = useState<{ status: string } | null>(null);
  const [opsConfig, setOpsConfig] = useState<OpsConfig | null>(null);
  const [parameters, setParameters] = useState<OpsParameters | null>(null);
  const [events, setEvents] = useState<OpsEvent[]>([]);
  const [llmRows, setLlmRows] = useState<OpsLlmRow[]>([]);

  // Verification review state (manual UUID entry)
  const [reviewId, setReviewId] = useState("");
  const [reviewAction, setReviewAction] = useState<"approve" | "reject">("approve");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewResult, setReviewResult] = useState<VerificationResponse | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) {
      return;
    }

    let isMounted = true;
    async function fetchAdminData() {
      setLoading(true);
      setError(null);
      try {
        const [statusData, readyData, healthData, cfgData, paramsData, eventsData, llmData] =
          await Promise.all([
            apiFetch<OpsStatus>("/ops/status"),
            apiFetch<{ ready: boolean; checks: Record<string, unknown> }>("/ready"),
            apiFetch<{ status: string }>("/health"),
            apiFetch<OpsConfig>("/ops/config"),
            apiFetch<OpsParameters>("/ops/parameters"),
            apiFetch<OpsEvent[]>("/ops/activity/events"),
            apiFetch<OpsLlmRow[]>("/ops/activity/llm"),
          ]);

        if (isMounted) {
          setOpsStatus(statusData);
          setReadyStatus(readyData);
          setHealthStatus(healthData);
          setOpsConfig(cfgData);
          setParameters(paramsData);
          setEvents(eventsData || []);
          setLlmRows(llmData || []);
        }
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
          setError("Failed to fetch operational administration data.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchAdminData();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, sessionChecked, router]);

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setReviewError(null);
    setReviewResult(null);

    const cleanId = reviewId.trim();
    if (!cleanId) {
      setReviewError("Please enter a valid verification UUID.");
      return;
    }

    setReviewSubmitting(true);
    try {
      const res = await apiFetch<VerificationResponse>(
        `/api/admin/verifications/${cleanId}/review`,
        {
          method: "POST",
          body: JSON.stringify({
            action: reviewAction,
            review_notes: reviewNotes.trim() || null,
          }),
        }
      );
      setReviewResult(res);
      setReviewId("");
      setReviewNotes("");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setReviewError(err.parsed.message);
      } else {
        setReviewError("Execution error submitting review decision.");
      }
    } finally {
      setReviewSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Validating admin permissions and loading ops telemetry...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>SYSTEM GOVERNANCE / OPS</span>
        <h1>Administration & Readiness Console</h1>
        <p className={styles.lead}>
          Readiness checks, configuration presence, parameter bounds, system events,
          LLM spend ledger, and institutional verification review.
        </p>
      </div>

      {error && (
        <StatusBanner
          status={httpStatus}
          message={error}
          type={httpStatus === 403 ? "warn" : "error"}
        />
      )}

      {/* System Health & Status Banner */}
      <section className={styles.card}>
        <h2>System Status & Readiness Probes</h2>
        <div className={styles.metricsGrid}>
          <div className={styles.metricCard}>
            <span className={styles.mLabel}>LIVENESS PROBE (/health)</span>
            <span className={styles.mValueOk} data-mono>{healthStatus?.status?.toUpperCase() || "--"}</span>
            <span className={styles.mSub}>FastAPI process heartbeat</span>
          </div>

          <div className={styles.metricCard}>
            <span className={styles.mLabel}>READINESS PROBE (/ready)</span>
            <span className={readyStatus?.ready ? styles.mValueOk : styles.mValueWarn} data-mono>
              {readyStatus?.ready ? "READY" : "NOT READY"}
            </span>
            <span className={styles.mSub}>Environment variables & groups verified</span>
          </div>

          <div className={styles.metricCard}>
            <span className={styles.mLabel}>CODE VERSION</span>
            <span className={styles.mValue} data-mono>{opsStatus?.code_version || "unknown"}</span>
            <span className={styles.mSub}>Git HEAD commit hash</span>
          </div>

          <div className={styles.metricCard}>
            <span className={styles.mLabel}>SERVER UPTIME</span>
            <span className={styles.mValue} data-mono>{opsStatus?.uptime_seconds}s</span>
            <span className={styles.mSub}>Monotonic seconds since boot</span>
          </div>
        </div>
      </section>

      {/* Institutional Verification Queue (Manual UUID Entry) */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <h2>Institutional Verification Decision Queue</h2>
          <span className={styles.gapNotice} data-mono>
            GAP NOTICE: Manual UUID Entry (No backend GET /verifications list endpoint)
          </span>
        </div>
        <p className={styles.cardLead}>
          Enter an institutional registration UUID to approve or reject. Approval automatically promotes the user profile to institutional_paid.
        </p>

        {reviewError && <StatusBanner message={reviewError} type="error" />}
        {reviewResult && (
          <StatusBanner
            status={200}
            message={`Verification ${reviewResult.id} reviewed: ${reviewResult.status.toUpperCase()}. Registration: ${reviewResult.regulator} - ${reviewResult.registration_number}`}
            type="ok"
          />
        )}

        <form onSubmit={handleReviewSubmit} className={styles.reviewForm}>
          <div className={styles.field}>
            <label htmlFor="review-id">Verification Record UUID</label>
            <input
              id="review-id"
              type="text"
              value={reviewId}
              onChange={(e) => setReviewId(e.target.value)}
              placeholder="e.g. 00000000-0000-0000-0000-000000000000"
              required
              disabled={reviewSubmitting}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="review-action">Decision Action</label>
            <select
              id="review-action"
              value={reviewAction}
              onChange={(e) => setReviewAction(e.target.value as "approve" | "reject")}
              disabled={reviewSubmitting}
            >
              <option value="approve">Approve (Upgrade to institutional_paid)</option>
              <option value="reject">Reject (Retain free institutional status)</option>
            </select>
          </div>

          <div className={styles.field}>
            <label htmlFor="review-notes">Audit Notes (Optional)</label>
            <input
              id="review-notes"
              type="text"
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              placeholder="e.g. Verified via SEBI public intermediary portal"
              disabled={reviewSubmitting}
            />
          </div>

          <button type="submit" className={styles.submitBtn} disabled={reviewSubmitting}>
            {reviewSubmitting ? "Executing Review..." : "Submit Verification Decision"}
          </button>
        </form>
      </section>

      {/* Environment Config Presence (Names only, never values) */}
      <section className={styles.card}>
        <h2>Configuration Variables Presence (Names Only)</h2>
        <p className={styles.cardLead}>
          Surfaces required environment variables partitioned by runtime group. Values are strictly redacted.
        </p>

        <div className={styles.configGroups}>
          {opsConfig?.groups &&
            Object.entries(opsConfig.groups).map(([groupName, vars]) => {
              const visibleVars = vars.filter((v) => !v.name.startsWith("SMTP_"));
              if (visibleVars.length === 0) return null;

              return (
                <div key={groupName} className={styles.configGroupBlock}>
                  <div className={styles.groupHeader} data-mono>
                    GROUP: {groupName.toUpperCase()}
                  </div>
                  <div className={styles.varList}>
                    {visibleVars.map((v) => {
                      const isGroupEnabled =
                        v.group_enabled !== undefined
                          ? v.group_enabled
                          : (opsConfig.enabled_groups?.includes(groupName) ?? false);

                      let badgeText = "present";
                      let badgeClass = styles.presOk;

                      if (!isGroupEnabled) {
                        badgeText = "not used: group not enabled";
                        badgeClass = styles.presNotEnabled;
                      } else if (!v.present) {
                        badgeText = "missing";
                        badgeClass = styles.presMissing;
                      } else {
                        badgeText = "present";
                        badgeClass = styles.presOk;
                      }

                      return (
                        <div key={v.name} className={styles.varRow}>
                          <span className={styles.varName} data-mono>{v.name}</span>
                          <span
                            className={`${styles.presenceBadge} ${badgeClass}`}
                            data-mono
                          >
                            {badgeText}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
        </div>
      </section>

      {/* Analytical Parameters Table with Bounds */}
      <section className={styles.card}>
        <h2>Loaded Analytical Parameters Register</h2>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Parameter Name</th>
              <th>Data Type</th>
              <th>Default Value</th>
              <th>Min Bound</th>
              <th>Max Bound</th>
              <th>Unit</th>
              <th>Override Allowed</th>
            </tr>
          </thead>
          <tbody>
            {parameters?.parameters &&
              Object.entries(parameters.parameters).map(([pName, pEntry]) => (
                <tr key={pName}>
                  <td className={styles.paramNameCell} data-mono>{pName}</td>
                  <td data-mono>{pEntry.type}</td>
                  <td data-mono>{String(pEntry.default)}</td>
                  <td data-mono>{pEntry.min !== null && pEntry.min !== undefined ? String(pEntry.min) : "--"}</td>
                  <td data-mono>{pEntry.max !== null && pEntry.max !== undefined ? String(pEntry.max) : "--"}</td>
                  <td data-mono>{pEntry.unit || "--"}</td>
                  <td data-mono>{pEntry.override_allowed ? "YES" : "NO"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>

      {/* Events Activity Log */}
      <section className={styles.card}>
        <h2>Recent System Events Log</h2>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Event ID</th>
              <th>Event Kind</th>
              <th>Subject</th>
              <th>Status</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {events.length > 0 ? (
              events.map((ev) => (
                <tr key={ev.id}>
                  <td className={styles.idCell} data-mono>{ev.id.slice(0, 8)}...</td>
                  <td data-mono>{ev.kind}</td>
                  <td data-mono>{ev.subject}</td>
                  <td>
                    <span
                      className={`${styles.statusBadge} ${
                        ev.status === "ok" || ev.status === "success"
                          ? styles.statusOk
                          : styles.statusWarn
                      }`}
                      data-mono
                    >
                      {ev.status.toUpperCase()}
                    </span>
                  </td>
                  <td data-mono>{ev.duration_ms ? `${ev.duration_ms}ms` : "--"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className={styles.emptyCell}>
                  No events logged in database.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* LLM Ledger Telemetry */}
      <section className={styles.card}>
        <h2>LLM Cost & Token Ledger</h2>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Ledger ID</th>
              <th>Route</th>
              <th>Model ID / Alias</th>
              <th>Input Tokens</th>
              <th>Output Tokens</th>
              <th>Estimated Cost</th>
              <th>Cache Hit</th>
            </tr>
          </thead>
          <tbody>
            {llmRows.length > 0 ? (
              llmRows.map((row) => (
                <tr key={row.id}>
                  <td className={styles.idCell} data-mono>{row.id.slice(0, 8)}...</td>
                  <td data-mono>{row.route}</td>
                  <td data-mono>{row.model_id} ({row.alias})</td>
                  <td data-mono>{row.input_tokens}</td>
                  <td data-mono>{row.output_tokens}</td>
                  <td data-mono>${formatDecimal(row.est_cost_usd, 4)}</td>
                  <td data-mono>{row.cache_hit ? "YES" : "NO"}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className={styles.emptyCell}>
                  No LLM calls recorded in ledger.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
