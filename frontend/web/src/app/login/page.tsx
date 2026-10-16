"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";
import { LoginResponse } from "@/types/api";
import { StatusBanner } from "@/components/StatusBanner";
import styles from "./login.module.css";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [httpStatus, setHttpStatus] = useState<number | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setErrorCode(null);
    setHttpStatus(null);

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setErrorMessage("Please enter both email and password.");
      return;
    }

    setLoading(true);
    try {
      const data = await apiFetch<LoginResponse>("/api/auth/token", {
        method: "POST",
        body: JSON.stringify({ email: cleanEmail, password }),
      });

      await login(data.access_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setHttpStatus(err.status);
        setErrorCode(err.parsed.code);
        setErrorMessage(err.parsed.message);
      } else {
        const errorObj = err as Error;
        setHttpStatus(503);
        setErrorCode("network_failure");
        setErrorMessage(
          `Network failure: unable to reach authentication server (${errorObj.message || "connection failed"}).`
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.pageContainer}>
      <div className={styles.authBox}>
        <div className={styles.header}>
          <span className={styles.badge} data-mono>ACCESS</span>
          <h1>Sign In</h1>
          <p>Deterministic forensic analytics. Enter your credentials to access your session.</p>
        </div>

        {errorMessage && (
          <StatusBanner
            status={httpStatus}
            message={errorMessage}
            type={httpStatus === 503 ? "warn" : "error"}
          />
        )}

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="login-email">Email Address</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@fininsight.local"
              required
              disabled={loading}
              autoComplete="email"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              disabled={loading}
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? "Authenticating..." : "Authenticate"}
          </button>
        </form>

        <div className={styles.footerRow}>
          <span>Don&apos;t have an account?</span>
          <Link href="/signup" className={styles.link}>
            Register for access
          </Link>
        </div>
      </div>
    </div>
  );
}
