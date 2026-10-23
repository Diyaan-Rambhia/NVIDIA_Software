"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useEffect,
  useRef,
} from "react";
import { UserProfileResponse, EntitlementsResponse } from "@/types/api";
import { apiFetch, setMemoryToken, ApiError } from "@/lib/api";

export interface SessionErrorState {
  status: number;
  code: string;
  message: string;
}

interface AuthContextType {
  token: string | null;
  user: UserProfileResponse | null;
  entitlements: EntitlementsResponse | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  idleMessage: string | null;
  sessionError: SessionErrorState | null;
  sessionChecked: boolean;
  login: (accessToken: string, refreshToken?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: (activeToken?: string) => Promise<void>;
  clearIdleMessage: () => void;
  clearSessionError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [entitlements, setEntitlements] = useState<EntitlementsResponse | null>(null);
  const [idleMessage, setIdleMessage] = useState<string | null>(null);
  const [sessionError, setSessionError] = useState<SessionErrorState | null>(null);
  const [sessionChecked, setSessionChecked] = useState<boolean>(false);

  // Single in-flight refresh call guard per tab
  const refreshingPromiseRef = useRef<Promise<string | null> | null>(null);
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastTouchTimeRef = useRef<number>(0);

  const clearIdleMessage = useCallback(() => {
    setIdleMessage(null);
  }, []);

  const clearSessionError = useCallback(() => {
    setSessionError(null);
  }, []);

  const logout = useCallback(async () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    setToken(null);
    setUser(null);
    setEntitlements(null);
    setMemoryToken(null);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignored
    }
  }, []);

  const refreshSession = useCallback(
    async (activeToken?: string) => {
      const t = activeToken || token;
      if (!t) return;
      try {
        const [profileData, entData] = await Promise.all([
          apiFetch<UserProfileResponse>("/api/auth/me", {}, t),
          apiFetch<EntitlementsResponse>("/api/entitlements", {}, t),
        ]);
        setUser(profileData);
        setEntitlements(entData);
      } catch {
        logout();
      }
    },
    [token, logout]
  );

  // Call /api/auth/session to exchange cookie for refreshed access token
  const executeSessionRefresh = useCallback(async (): Promise<string | null> => {
    if (refreshingPromiseRef.current) {
      return refreshingPromiseRef.current;
    }

    const run = async () => {
      try {
        const res = await fetch("/api/auth/session", { method: "POST" });
        if (!res.ok) {
          const status = res.status;
          const data = await res.json().catch(() => ({}));
          const code = data.code || (status === 401 ? "unauthorized" : "session_error");
          const message = data.message || (status === 401 ? "Session expired or not found" : "Session check failed");

          if (data.code === "idle_timeout") {
            setIdleMessage("Signed out after 5 hours of no use.");
          } else if (data.code && data.code !== "no_session") {
            // Explicitly surface failed session check status and message
            setSessionError({ status, code, message });
          }
          await logout();
          return null;
        }

        const data = await res.json();
        const newAccessToken = data.access_token;
        if (newAccessToken) {
          setToken(newAccessToken);
          setMemoryToken(newAccessToken);
          setSessionError(null);
          setIdleMessage(null);

          // Schedule next background refresh before access token expires (default 15m)
          const expiresInSec = typeof data.expires_in === "number" ? data.expires_in : 900;
          const refreshDelayMs = Math.max(30000, (expiresInSec - 60) * 1000);

          if (refreshTimerRef.current) {
            clearTimeout(refreshTimerRef.current);
          }
          refreshTimerRef.current = setTimeout(() => {
            executeSessionRefresh();
          }, refreshDelayMs);

          await refreshSession(newAccessToken);
          return newAccessToken;
        }
        await logout();
        return null;
      } catch {
        return null;
      } finally {
        setSessionChecked(true);
        refreshingPromiseRef.current = null;
      }
    };

    refreshingPromiseRef.current = run();
    return refreshingPromiseRef.current;
  }, [logout, refreshSession]);

  const login = useCallback(
    async (newToken: string, refreshToken?: string) => {
      setIdleMessage(null);
      setSessionError(null);

      if (!refreshToken) {
        throw new ApiError(
          422,
          {
            status: 422,
            code: "missing_refresh_token",
            message: "Missing refresh_token in login response from backend.",
          },
          null
        );
      }

      const loginRes = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_token: newToken,
          refresh_token: refreshToken,
        }),
      });

      if (!loginRes.ok) {
        const errData = await loginRes.json().catch(() => ({}));
        throw new ApiError(
          loginRes.status,
          {
            status: loginRes.status,
            code: errData.code || "login_failed",
            message: errData.message || "Failed to establish session.",
          },
          errData
        );
      }

      // Verify browser accepted and sent back the cookie via /api/auth/session
      const sessionVerify = await fetch("/api/auth/session", { method: "POST" });
      if (!sessionVerify.ok) {
        const verifyData = await sessionVerify.json().catch(() => ({}));
        throw new ApiError(
          400,
          {
            status: 400,
            code: "cookie_storage_failed",
            message:
              "Browser was unable to store the session cookie. Check cookie permissions and security settings.",
          },
          verifyData
        );
      }

      setToken(newToken);
      setMemoryToken(newToken);
      setSessionChecked(true);

      await refreshSession(newToken);
    },
    [refreshSession]
  );

  // Deliberate user action triggers touch endpoint (throttled to at most once per 30s)
  const reportUserAction = useCallback(async () => {
    const now = Date.now();
    if (now - lastTouchTimeRef.current < 30000) {
      return;
    }
    lastTouchTimeRef.current = now;
    try {
      const res = await fetch("/api/auth/touch", { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data.code === "idle_timeout") {
          setIdleMessage("Signed out after 5 hours of no use.");
          await logout();
        }
      }
    } catch {
      // Ignored
    }
  }, [logout]);

  // On page load, check session route once
  useEffect(() => {
    executeSessionRefresh();

    // Listen for deliberate user actions
    const handleAction = () => {
      reportUserAction();
    };

    window.addEventListener("click", handleAction, { passive: true });
    window.addEventListener("keydown", handleAction, { passive: true });

    return () => {
      window.removeEventListener("click", handleAction);
      window.removeEventListener("keydown", handleAction);
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [executeSessionRefresh, reportUserAction]);

  const isAdmin = useMemo(() => {
    return Boolean(user && (user.role === "admin" || user.role === "judge"));
  }, [user]);

  const value = useMemo(
    () => ({
      token,
      user,
      entitlements,
      isAuthenticated: Boolean(token),
      isAdmin,
      idleMessage,
      sessionError,
      sessionChecked,
      login,
      logout,
      refreshSession,
      clearIdleMessage,
      clearSessionError,
    }),
    [
      token,
      user,
      entitlements,
      isAdmin,
      idleMessage,
      sessionError,
      sessionChecked,
      login,
      logout,
      refreshSession,
      clearIdleMessage,
      clearSessionError,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
