"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { EntitlementsResponse, UserProfileResponse } from "@/types/api";
import { StatusBanner } from "@/components/StatusBanner";
import { ArrowRightIcon, LockIcon, CheckIcon, AlertIcon } from "@/components/Icons";
import styles from "./dashboard.module.css";

interface ToolRow {
  key: string;
  name: string;
  route: string;
  state: string;
  status: number;
  remainingQuota: number | null;
  reason: string;
  allowed: boolean;
}

export default function DashboardPage() {
  const router = useRouter();
  const { token, isAuthenticated, refreshSession } = useAuth();

  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [entitlements, setEntitlements] = useState<EntitlementsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
      return;
    }

    let isMounted = true;
    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const [meData, entData] = await Promise.all([
          apiFetch<UserProfileResponse>("/api/auth/me"),
          apiFetch<EntitlementsResponse>("/api/entitlements"),
        ]);
        if (isMounted) {
          setProfile(meData);
          setEntitlements(entData);
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
          setError("Network error fetching entitlements.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, token, router]);

  // Transform entitlements into tool rows
  const tools: ToolRow[] = React.useMemo(() => {
    const f1 = entitlements?.features?.feature1_contagion;
    const f2 = entitlements?.features?.feature2_filings;
    const f3 = entitlements?.features?.feature3_forensic;

    return [
      {
        key: "feature1",
        name: "Feature 1: Systemic Contagion & Absorption",
        route: "/contagion",
        state: f1 ? (f1.status === 403 ? "403 Denied" : f1.status === 402 ? "402 Upgrade" : f1.decision.toUpperCase()) : "UNKNOWN",
        status: f1?.status || 0,
        remainingQuota: f1?.remaining_quota ?? null,
        reason: f1?.reason || (f1?.status === 403 ? "Segment restricted: Institutional plan required" : f1?.status === 402 ? "Upgrade required" : "Granted by plan"),
        allowed: Boolean(f1?.allowed),
      },
      {
        key: "feature2",
        name: "Feature 2: XBRL Filings Consistency Auditor",
        route: "/filings",
        state: f2 ? (f2.status === 402 ? "402 Upgrade" : f2.decision.toUpperCase()) : "UNKNOWN",
        status: f2?.status || 0,
        remainingQuota: f2?.remaining_quota ?? null,
        reason: f2?.reason || "Daily quota applies",
        allowed: Boolean(f2?.allowed),
      },
      {
        key: "feature3",
        name: "Feature 3: Trade Log Forensic Review & XIRR",
        route: "/trade-log",
        state: f3 ? (f3.status === 402 ? "402 Upgrade" : f3.decision.toUpperCase()) : "UNKNOWN",
        status: f3?.status || 0,
        remainingQuota: f3?.remaining_quota ?? null,
        reason: f3?.reason || "Daily quota applies",
        allowed: Boolean(f3?.allowed),
      },
    ];
  }, [entitlements]);

  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Loading session and analytical entitlements...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageContainer}>
      <div className={styles.headerRow}>
        <div>
          <span className={styles.badge} data-mono>OVERVIEW</span>
          <h1>Analytical Dashboard</h1>
          <p className={styles.subhead}>
            Active session: <span data-mono>{profile?.email}</span> [{profile?.segment?.toUpperCase()}]
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link href="/agent" className={styles.agentButton}>
            <span>Open Autonomous Agent</span>
            <ArrowRightIcon size={14} />
          </Link>
        </div>
      </div>

      {error && <StatusBanner status={httpStatus} message={error} type="error" />}

      {/* Quotas & Entitlement Summary */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricBlock}>
          <span className={styles.mLabel}>ASSIGNED PLAN</span>
          <span className={styles.mValue} data-mono>{profile?.plan?.toUpperCase()}</span>
          <span className={styles.mSub}>Segment: {profile?.segment?.toUpperCase()}</span>
        </div>

        <div className={styles.metricBlock}>
          <span className={styles.mLabel}>ROLE ACCESS</span>
          <span className={styles.mValue} data-mono>{profile?.role?.toUpperCase()}</span>
          <span className={styles.mSub}>Account Status: {profile?.status?.toUpperCase()}</span>
        </div>

        <div className={styles.metricBlock}>
          <span className={styles.mLabel}>TODAY&apos;S QUOTA LIMITS</span>
          <span className={styles.mValue} data-mono>
            {entitlements?.features?.feature2_filings?.remaining_quota !== null && entitlements?.features?.feature2_filings?.remaining_quota !== undefined
              ? `${entitlements.features.feature2_filings.remaining_quota} analyses remaining`
              : "Unlimited"}
          </span>
          <span className={styles.mSub}>
            Reset Boundary: {entitlements?.features?.feature2_filings?.reset_time ? `Resets at ${entitlements.features.feature2_filings.reset_time}` : "UTC Midnight"}
          </span>
        </div>
      </div>

      {/* Tools Access Table */}
      <section className={styles.tableSection}>
        <div className={styles.sectionTitleRow}>
          <h2>Feature Entitlements & Access State</h2>
        </div>

        <table className={styles.table}>
          <thead>
            <tr>
              <th>Analytical Tool</th>
              <th>Entitlement State</th>
              <th>Remaining Quota</th>
              <th>Access Reason / Governance</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => (
              <tr key={tool.key}>
                <td className={styles.toolNameCell}>
                  <Link href={tool.route} className={styles.toolLink}>
                    {tool.name}
                  </Link>
                </td>
                <td>
                  <span
                    className={`${styles.stateBadge} ${
                      tool.status === 200
                        ? styles.stateOk
                        : tool.status === 402 || tool.status === 403
                        ? styles.stateBlocked
                        : styles.stateWarn
                    }`}
                    data-mono
                  >
                    {tool.state}
                  </span>
                </td>
                <td data-mono>
                  {tool.remainingQuota !== null ? `${tool.remainingQuota} remaining` : "N/A"}
                </td>
                <td className={styles.reasonCell}>{tool.reason}</td>
                <td>
                  {tool.allowed ? (
                    <Link href={tool.route} className={styles.openBtn}>
                      Launch
                    </Link>
                  ) : (
                    <span className={styles.lockedBtn}>
                      <LockIcon size={12} />
                      <span>Restricted</span>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
