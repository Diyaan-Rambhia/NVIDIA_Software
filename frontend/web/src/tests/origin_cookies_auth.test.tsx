import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { checkOrigin } from "@/lib/origin";
import {
  isRequestSecure,
  getSessionCookieOptions,
  getClearSessionCookieOptions,
} from "@/lib/session_cookie";
import LoginPage from "@/app/login/page";
import * as apiModule from "@/lib/api";
import { ApiError } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const mockLogin = vi.fn();
const mockClearSessionError = vi.fn();
let mockSessionError: { status: number; code: string; message: string } | null = null;
let mockIdleMessage: string | null = null;

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    login: mockLogin,
    idleMessage: mockIdleMessage,
    sessionError: mockSessionError,
    clearSessionError: mockClearSessionError,
  }),
}));

describe("Origin Verification Logic", () => {
  it("accepts identical Origin host and Host header", () => {
    const req = new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: {
        origin: "http://localhost:3000",
        host: "localhost:3000",
      },
    });
    const result = checkOrigin(req);
    expect(result.allowed).toBe(true);
  });

  it("rejects untrusted mismatched Origin with origin_rejected code", () => {
    const req = new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: {
        origin: "http://attacker.example.com",
        host: "localhost:3000",
      },
    });
    const result = checkOrigin(req);
    expect(result.allowed).toBe(false);
    expect(result.code).toBe("origin_rejected");
  });

  it("accepts localhost versus 127.0.0.1 via configured loopback list", () => {
    // Origin is 127.0.0.1:3000 while request Host header is localhost:3000
    const req = new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: {
        origin: "http://127.0.0.1:3000",
        host: "localhost:3000",
      },
    });
    const result = checkOrigin(req);
    expect(result.allowed).toBe(true);
  });
});

describe("Cookie Flag Security for HTTP and HTTPS", () => {
  const originalEnv = process.env.NODE_ENV;

  beforeEach(() => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "test";
  });

  it("configures non-secure cookie for plain HTTP request in development/test", () => {
    const req = new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: {
        host: "localhost:3000",
      },
    });
    expect(isRequestSecure(req)).toBe(false);
    const opts = getSessionCookieOptions(req);
    expect(opts.secure).toBe(false);
    expect(opts.httpOnly).toBe(true);
    expect(opts.sameSite).toBe("lax");
    expect(opts.path).toBe("/api/auth");
  });

  it("configures Secure flag for HTTPS requests via URL protocol", () => {
    const req = new Request("https://fininsight.example.com/api/auth/login", {
      method: "POST",
      headers: {
        host: "fininsight.example.com",
      },
    });
    expect(isRequestSecure(req)).toBe(true);
    const opts = getSessionCookieOptions(req);
    expect(opts.secure).toBe(true);
    expect(opts.httpOnly).toBe(true);
    expect(opts.sameSite).toBe("lax");
    expect(opts.path).toBe("/api/auth");
  });

  it("configures Secure flag for requests with x-forwarded-proto: https", () => {
    const req = new Request("http://fininsight.example.com/api/auth/login", {
      method: "POST",
      headers: {
        host: "fininsight.example.com",
        "x-forwarded-proto": "https",
      },
    });
    expect(isRequestSecure(req)).toBe(true);
    const opts = getSessionCookieOptions(req);
    expect(opts.secure).toBe(true);
  });

  it("forces Secure flag when NODE_ENV is production", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "production";
    const req = new Request("http://localhost:3000/api/auth/login", {
      method: "POST",
      headers: {
        host: "localhost:3000",
      },
    });
    expect(isRequestSecure(req)).toBe(true);
    const opts = getSessionCookieOptions(req);
    expect(opts.secure).toBe(true);
    (process.env as Record<string, string | undefined>).NODE_ENV = originalEnv;
  });

  it("returns maxAge 0 for clear cookie options", () => {
    const req = new Request("http://localhost:3000/api/auth/logout", {
      method: "POST",
    });
    const opts = getClearSessionCookieOptions(req);
    expect(opts.maxAge).toBe(0);
    expect(opts.httpOnly).toBe(true);
  });
});

describe("Login Page Error Display", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockClearSessionError.mockReset();
    mockSessionError = null;
    mockIdleMessage = null;
    vi.restoreAllMocks();
  });

  it("renders HTTP status and error code when authentication fails", async () => {
    vi.spyOn(apiModule, "apiFetch").mockRejectedValue(
      new ApiError(
        401,
        {
          status: 401,
          code: "invalid_credentials",
          message: "Invalid email or password",
        },
        null
      )
    );

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: "test@fininsight.local" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Authenticate/i }));

    await waitFor(() => {
      expect(screen.getByText("HTTP 401")).toBeDefined();
      expect(screen.getByText("invalid_credentials")).toBeDefined();
      expect(screen.getByText(/Invalid email or password/i)).toBeDefined();
    });
  });

  it("renders error with code missing_refresh_token if backend token response lacks refresh token", async () => {
    vi.spyOn(apiModule, "apiFetch").mockResolvedValue({
      access_token: "mock-access-token",
      user_id: "00000000-0000-0000-0000-000000000001",
      token_type: "bearer",
      refresh_token: null, // missing refresh token
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: "test@fininsight.local" },
    });
    fireEvent.change(screen.getByLabelText(/Password/i), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Authenticate/i }));

    await waitFor(() => {
      expect(screen.getByText("HTTP 422")).toBeDefined();
      expect(screen.getByText("missing_refresh_token")).toBeDefined();
      expect(screen.getByText(/missing required field: refresh_token/i)).toBeDefined();
    });
  });

  it("renders status and code from failed session check", () => {
    mockSessionError = {
      status: 403,
      code: "origin_rejected",
      message: "Origin header rejected by server.",
    };

    render(<LoginPage />);

    expect(screen.getByText("HTTP 403")).toBeDefined();
    expect(screen.getByText("origin_rejected")).toBeDefined();
    expect(screen.getByText(/Origin header rejected by server/i)).toBeDefined();
  });
});
