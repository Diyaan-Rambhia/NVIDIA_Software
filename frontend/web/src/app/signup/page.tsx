"use client";

import React, { useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api";
import { SignUpResponse } from "@/types/api";
import { StatusBanner } from "@/components/StatusBanner";
import styles from "./signup.module.css";

export default function SignUpPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [segment, setSegment] = useState<"retail" | "institutional">("retail");
  const [tosAccepted, setTosAccepted] = useState(false);

  const [loading, setLoading] = useState(false);
  const [successData, setSuccessData] = useState<SignUpResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setHttpStatus(null);

    if (!tosAccepted) {
      setErrorMessage("You must accept the Terms of Service and Educational Disclaimer to register.");
      return;
    }

    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }

    setLoading(true);
    try {
      const data = await apiFetch<SignUpResponse>("/api/auth/signup", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
          segment,
          tos_accepted: tosAccepted,
          tos_version: "v1",
        }),
      });

      setSuccessData(data);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setHttpStatus(err.status);
        setErrorMessage(err.parsed.message);
      } else {
        const errorObj = err as Error;
        setHttpStatus(503);
        setErrorMessage(`Network failure: ${errorObj.message || "unable to connect"}`);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.authBox}>
        <div className={styles.header}>
          <span className={styles.badge} data-mono>REGISTRATION</span>
          <h1>Create Account</h1>
          <p>Select your market segment to configure institutional or retail entitlement boundaries.</p>
        </div>

        {errorMessage && (
          <StatusBanner
            status={httpStatus}
            message={errorMessage}
            type="error"
          />
        )}

        {successData ? (
          <div className={styles.successBox}>
            <StatusBanner
              status={200}
              message={successData.message}
              type="ok"
            />
            <div className={styles.successDetails}>
              <div><strong>Registered Email:</strong> {successData.email}</div>
              <div><strong>Segment:</strong> {successData.segment.toUpperCase()}</div>
              <div><strong>Initial Plan:</strong> {successData.plan.toUpperCase()}</div>
            </div>
            <Link href="/login" className={styles.primaryLink}>
              Proceed to Sign In
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="signup-email">Email Address</label>
              <input
                id="signup-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@firm.com"
                required
                disabled={loading}
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="signup-password">Password (min 8 characters)</label>
              <input
                id="signup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
                disabled={loading}
              />
            </div>

            <div className={styles.field}>
              <label htmlFor="signup-segment">Market Participant Segment</label>
              <select
                id="signup-segment"
                value={segment}
                onChange={(e) => setSegment(e.target.value as "retail" | "institutional")}
                disabled={loading}
              >
                <option value="retail">Retail Individual (Features 2 & 3, Agent)</option>
                <option value="institutional">Institutional / Regulated Firm (Systemic Scan, XBRL Auditor)</option>
              </select>
            </div>

            <div className={styles.checkboxField}>
              <input
                id="signup-tos"
                type="checkbox"
                checked={tosAccepted}
                onChange={(e) => setTosAccepted(e.target.checked)}
                disabled={loading}
              />
              <label htmlFor="signup-tos">
                I accept the Educational Terms of Service and acknowledge that FinFriend does not provide investment recommendations or SEBI financial advice.
              </label>
            </div>

            <button type="submit" className={styles.submitBtn} disabled={loading}>
              {loading ? "Registering..." : "Create Account"}
            </button>
          </form>
        )}

        <div className={styles.footerRow}>
          <span>Already registered?</span>
          <Link href="/login" className={styles.link}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
