import { ErrorEnvelope } from "@/types/api";

export interface ParsedApiError {
  status: number;
  code: string;
  message: string;
  resetTime?: string | null;
  upgradeTargets?: string[] | null;
}

export function parseApiError(status: number, data: unknown): ParsedApiError {
  let code = `HTTP_${status}`;
  let message = `Request failed with HTTP status ${status}`;
  let resetTime: string | null = null;
  let upgradeTargets: string[] | null = null;

  if (data && typeof data === "object") {
    const env = data as Partial<ErrorEnvelope> & { detail?: unknown; error?: unknown; reset_time?: string };

    if (env.error && typeof env.error === "object") {
      const err = env.error as unknown as Record<string, unknown>;
      code = String(err.code || code);
      message = String(err.message || message);
      if (err.reset_time) resetTime = String(err.reset_time);
      if (Array.isArray(err.upgrade_targets)) upgradeTargets = err.upgrade_targets as string[];
    } else if (env.detail) {
      if (typeof env.detail === "string") {
        message = env.detail;
      } else if (typeof env.detail === "object") {
        const det = env.detail as Record<string, unknown>;
        code = String(det.code || code);
        message = String(det.message || det.code || JSON.stringify(det));
        if (det.reset_time) resetTime = String(det.reset_time);
        if (Array.isArray(det.upgrade_targets)) upgradeTargets = det.upgrade_targets as string[];
      }
    }

    if (!resetTime && env.reset_time) {
      resetTime = String(env.reset_time);
    }
  }

  // Ensure standard messages according to HTTP status code if not provided by backend
  if (status === 401) {
    code = code.startsWith("HTTP") ? "UNAUTHORIZED" : code;
    if (!message || message.startsWith("Request failed")) {
      message = "Authentication required. Please log in.";
    }
  } else if (status === 402) {
    code = code.startsWith("HTTP") ? "PAYMENT_REQUIRED" : code;
    if (!message || message.startsWith("Request failed")) {
      message = "Upgrade required to access this feature.";
    }
  } else if (status === 403) {
    code = code.startsWith("HTTP") ? "FORBIDDEN" : code;
    if (!message || message.startsWith("Request failed")) {
      message = "Access denied for your account segment.";
    }
  } else if (status === 429) {
    code = code.startsWith("HTTP") ? "QUOTA_EXCEEDED" : code;
    if (!message || message.startsWith("Request failed")) {
      message = "Daily analytical quota reached.";
    }
  } else if (status === 503) {
    code = code.startsWith("HTTP") ? "SERVICE_UNAVAILABLE" : code;
    if (!message || message.startsWith("Request failed")) {
      message = "Service temporarily unavailable.";
    }
  }

  return {
    status,
    code,
    message,
    resetTime,
    upgradeTargets,
  };
}
