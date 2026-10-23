import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  parseSession,
  isSessionIdleTimedOut,
  sessionAfterUserAction,
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

  // Update last_activity to current timestamp on user action
  const updatedCookie = sessionAfterUserAction(sessionCookie, Date.now());
  cookieStore.set(
    "finfriend_session",
    updatedCookie,
    getSessionCookieOptions(req)
  );

  return NextResponse.json({ ok: true });
}
