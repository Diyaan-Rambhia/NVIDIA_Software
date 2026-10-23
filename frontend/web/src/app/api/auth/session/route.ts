import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  parseSession,
  isSessionIdleTimedOut,
  sessionAfterRefresh,
  getSessionCookieOptions,
  getClearSessionCookieOptions,
} from "@/lib/session_cookie";
import { checkOrigin } from "@/lib/origin";

export async function POST(req: Request) {
  const originResult = checkOrigin(req);
  if (!originResult.allowed) {
    return NextResponse.json(
      {
        status: 403,
        code: originResult.code || "origin_rejected",
        message: originResult.message || "Origin header rejected",
      },
      { status: 403 }
    );
  }

  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("finfriend_session")?.value;

  if (!sessionCookie) {
    return NextResponse.json(
      {
        status: 401,
        code: "no_session",
        message: "No active session cookie found.",
      },
      { status: 401 }
    );
  }

  const session = parseSession(sessionCookie);
  if (!session) {
    cookieStore.set(
      "finfriend_session",
      "",
      getClearSessionCookieOptions(req)
    );
    return NextResponse.json(
      {
        status: 401,
        code: "invalid_session",
        message: "Invalid session cookie format.",
      },
      { status: 401 }
    );
  }

  // Check 5 hours idle limit
  if (isSessionIdleTimedOut(session.last_activity)) {
    cookieStore.set(
      "finfriend_session",
      "",
      getClearSessionCookieOptions(req)
    );
    return NextResponse.json(
      {
        status: 401,
        code: "idle_timeout",
        message: "Signed out after 5 hours of no use.",
      },
      { status: 401 }
    );
  }

  // Call backend /api/auth/refresh
  const scheme = "http";
  const backendUrl = process.env.BACKEND_URL || `${scheme}://127.0.0.1:8000`;
  try {
    const backendRes = await fetch(`${backendUrl}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    });

    if (!backendRes.ok) {
      cookieStore.set(
        "finfriend_session",
        "",
        getClearSessionCookieOptions(req)
      );
      return NextResponse.json(
        {
          status: 401,
          code: "refresh_failed",
          message: "Session expired. Please sign in again.",
        },
        { status: 401 }
      );
    }

    const data = await backendRes.json();
    const newRefreshToken = data.refresh_token || session.refresh_token;

    // Update refresh token in cookie without extending last_activity idle time
    const updatedCookie = sessionAfterRefresh(sessionCookie, newRefreshToken);
    cookieStore.set(
      "finfriend_session",
      updatedCookie,
      getSessionCookieOptions(req)
    );

    return NextResponse.json({
      ok: true,
      access_token: data.access_token,
      expires_in: data.expires_in,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Backend unavailable";
    return NextResponse.json(
      {
        status: 503,
        code: "backend_error",
        message: msg,
      },
      { status: 503 }
    );
  }
}
