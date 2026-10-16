import React from "react";
import { ParsedApiError } from "@/lib/errors";
import { AlertIcon, CheckIcon, LockIcon } from "./Icons";
import styles from "./StatusBanner.module.css";

interface StatusBannerProps {
  error?: ParsedApiError | null;
  message?: string | null;
  status?: number | string | null;
  type?: "error" | "warn" | "upgrade" | "ok" | "info" | "empty";
  emptyReason?: string | null;
}

export function StatusBanner({ error, message, status, type, emptyReason }: StatusBannerProps) {
  if (!error && !message && !emptyReason) return null;

  const effectiveStatus = error ? error.status : status;
  const effectiveMessage = error ? error.message : (message || emptyReason);
  
  let effectiveType = type || "error";
  if (error) {
    if (error.status === 402 || error.status === 429) {
      effectiveType = "upgrade";
    } else if (error.status === 403) {
      effectiveType = "warn";
    } else if (error.status === 200) {
      effectiveType = "ok";
    } else {
      effectiveType = "error";
    }
  } else if (emptyReason) {
    effectiveType = "info";
  }

  const badgeClass =
    effectiveType === "ok"
      ? styles.badgeOk
      : effectiveType === "upgrade" || effectiveType === "warn"
      ? styles.badgeWarn
      : effectiveType === "info"
      ? styles.badgeInfo
      : styles.badgeFail;

  return (
    <div className={`${styles.banner} ${badgeClass}`} role="alert">
      <div className={styles.iconContainer}>
        {effectiveType === "ok" && <CheckIcon size={16} />}
        {effectiveType === "upgrade" && <LockIcon size={16} />}
        {(effectiveType === "warn" || effectiveType === "error") && <AlertIcon size={16} />}
      </div>
      <div className={styles.content}>
        <div className={styles.headerRow}>
          {effectiveStatus && (
            <span className={styles.statusBadge} data-mono>
              HTTP {effectiveStatus}
            </span>
          )}
          {error?.code && (
            <span className={styles.codeBadge} data-mono>
              {error.code}
            </span>
          )}
        </div>
        <div className={styles.messageText}>{effectiveMessage}</div>
        {error?.resetTime && (
          <div className={styles.resetText} data-mono>
            Quota resets at: {error.resetTime}
          </div>
        )}
        {error?.upgradeTargets && error.upgradeTargets.length > 0 && (
          <div className={styles.upgradeText}>
            Required plan: {error.upgradeTargets.join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}
