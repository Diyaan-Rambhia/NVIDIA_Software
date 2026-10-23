"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { UserProfileResponse, EntitlementsResponse, VerificationResponse } from "@/types/api";
import { StatusBanner } from "@/components/StatusBanner";
import styles from "./account.module.css";

export default function AccountPage() {
  const router = useRouter();
  const { isAuthenticated, sessionChecked, refreshSession } = useAuth();

  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfileResponse | null>(null);
  const [entitlements, setEntitlements] = useState<EntitlementsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  // Verification form state
  const [regulator, setRegulator] = useState("SEBI");
  const [regNumber, setRegNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verificationResult, setVerificationResult] = useState<VerificationResponse | null>(null);
  const [verificationError, setVerificationError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push("/login");
      return;
    }
    if (!isAuthenticated) {
      return;
    }

    let isMounted = true;
    async function fetchAccountData() {
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
          setError("Failed to load account profile.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchAccountData();
    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, sessionChecked, router]);

  const handleVerificationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerificationError(null);
    setVerificationResult(null);

    if (!regNumber.trim()) {
      setVerificationError("Please enter your registration number.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiFetch<VerificationResponse>("/api/verifications", {
        method: "POST",
        body: JSON.stringify({
          regulator: regulator.trim(),
          registration_number: regNumber.trim(),
        }),
      });
      setVerificationResult(res);
      setRegNumber("");
      await refreshSession();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setVerificationError(err.parsed.message);
      } else {
        setVerificationError("Failed to submit verification request.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Loading account profile and quota register...</span>
        </div>
      </div>
    );
  }

  const isInstitutional = profile?.segment === "institutional";

  return (
    <div className={styles.pageContainer}>
      <div className={styles.header}>
        <span className={styles.badge} data-mono>PROFILE & CREDENTIALS</span>
        <h1>Account Settings</h1>
        <p>Review active plan entitlements, daily quota caps, and regulator verification credentials.</p>
      </div>

      {error && <StatusBanner status={httpStatus} message={error} type="error" />}

      {/* Account Profile Card */}
      <section className={styles.card}>
        <h2>Account Identity</h2>
        <div className={styles.grid2}>
          <div className={styles.metaRow}>
            <span className={styles.label}>Email Address</span>
            <span className={styles.val} data-mono>{profile?.email}</span>
          </div>
          <div className={styles.metaRow}>
            <span className={styles.label}>User UUID</span>
            <span className={styles.valSmall} data-mono>{profile?.user_id}</span>
          </div>
          <div className={styles.metaRow}>
            <span className={styles.label}>Market Segment</span>
            <span className={styles.val} data-mono>{profile?.segment?.toUpperCase()}</span>
          </div>
          <div className={styles.metaRow}>
            <span className={styles.label}>Active Plan</span>
            <span className={styles.val} data-mono>{profile?.plan?.toUpperCase()}</span>
          </div>
          <div className={styles.metaRow}>
            <span className={styles.label}>Account Role</span>
            <span className={styles.val} data-mono>{profile?.role?.toUpperCase()}</span>
          </div>
          <div className={styles.metaRow}>
            <span className={styles.label}>TOS Agreement Version</span>
            <span className={styles.val} data-mono>{profile?.tos_accepted_version || "N/A"}</span>
          </div>
        </div>
      </section>

      {/* Daily Quotas Card */}
      <section className={styles.card}>
        <h2>Daily Quotas & Reset Cadence</h2>
        <p className={styles.cardLead}>
          Quotas are calculated strictly on daily UTC boundaries. No rollover.
        </p>
        <div className={styles.quotaList}>
          {entitlements?.features &&
            Object.entries(entitlements.features).map(([key, detail]) => {
              if (!detail) return null;
              return (
                <div key={key} className={styles.quotaItem}>
                  <div className={styles.quotaName}>
                    <strong>{key.replace("_", " ").toUpperCase()}</strong>
                    <span className={styles.quotaState} data-mono>
                      {detail.decision.toUpperCase()}
                    </span>
                  </div>
                  <div className={styles.quotaDetails} data-mono>
                    {detail.remaining_quota !== null && detail.remaining_quota !== undefined
                      ? `${detail.remaining_quota} analyses remaining`
                      : detail.decision === "full"
                      ? "Unlimited access"
                      : "Locked / Restricted"}
                  </div>
                </div>
              );
            })}
        </div>
      </section>

      {/* Institutional Verification Form */}
      <section className={styles.card}>
        <h2>Institutional Regulator Verification</h2>
        <p className={styles.cardLead}>
          Regulated asset managers, mutual funds, and FPIs submit official regulator registration numbers
          (e.g., SEBI INP/INA, RBI NBFC) to unlock institutional features.
        </p>

        {!isInstitutional ? (
          <div className={styles.noticeBox}>
            <strong>Notice:</strong> Your current account segment is{" "}
            <span data-mono>{profile?.segment?.toUpperCase()}</span>. Verification is reserved
            exclusively for institutional accounts.
          </div>
        ) : (
          <div>
            {verificationError && (
              <StatusBanner message={verificationError} type="error" />
            )}

            {verificationResult && (
              <StatusBanner
                status={200}
                message={`Verification request submitted successfully. Status: ${verificationResult.status.toUpperCase()} (ID: ${verificationResult.id})`}
                type="ok"
              />
            )}

            <form onSubmit={handleVerificationSubmit} className={styles.form}>
              <div className={styles.field}>
                <label htmlFor="regulator-select">Regulator Body</label>
                <select
                  id="regulator-select"
                  value={regulator}
                  onChange={(e) => setRegulator(e.target.value)}
                  disabled={submitting}
                >
                  <option value="SEBI">SEBI (Securities and Exchange Board of India)</option>
                  <option value="RBI">RBI (Reserve Bank of India)</option>
                  <option value="IRDAI">IRDAI (Insurance Regulatory & Development Authority)</option>
                  <option value="PFRDA">PFRDA (Pension Fund Regulatory & Development Authority)</option>
                </select>
              </div>

              <div className={styles.field}>
                <label htmlFor="reg-number">Registration / License Number</label>
                <input
                  id="reg-number"
                  type="text"
                  value={regNumber}
                  onChange={(e) => setRegNumber(e.target.value)}
                  placeholder="e.g. INZ000000000 or INP000000000"
                  required
                  disabled={submitting}
                />
              </div>

              <button type="submit" className={styles.submitBtn} disabled={submitting}>
                {submitting ? "Submitting..." : "Submit Registration for Audit"}
              </button>
            </form>
          </div>
        )}
      </section>
    </div>
  );
}
