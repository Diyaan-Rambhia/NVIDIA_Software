"use client";

import React, { createContext, useContext, useState, useCallback, useMemo } from "react";
import { UserProfileResponse, EntitlementsResponse } from "@/types/api";
import { apiFetch, setMemoryToken } from "@/lib/api";

interface AuthContextType {
  token: string | null;
  user: UserProfileResponse | null;
  entitlements: EntitlementsResponse | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfileResponse | null>(null);
  const [entitlements, setEntitlements] = useState<EntitlementsResponse | null>(null);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setEntitlements(null);
    setMemoryToken(null);
  }, []);

  const refreshSession = useCallback(async (activeToken?: string) => {
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
      // If fetching me/entitlements fails with invalid token, logout
      logout();
    }
  }, [token, logout]);

  const login = useCallback(async (newToken: string) => {
    setToken(newToken);
    setMemoryToken(newToken);
    await refreshSession(newToken);
  }, [refreshSession]);

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
      login,
      logout,
      refreshSession,
    }),
    [token, user, entitlements, isAdmin, login, logout, refreshSession]
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
