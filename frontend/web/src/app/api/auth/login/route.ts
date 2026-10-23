import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { serializeSession, getSessionCookieOptions } from "@/lib/session_cookie";
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

  try {
    const body = await req.json();
    const { refresh_token, access_token } = body;

    if (!refresh_token) {
      return NextResponse.json(
        {
          status: 400,
          code: "missing_refresh_token",
          message: "Missing refresh_token in login request",
        },
        { status: 400 }
      );
    }

    const sessionPayload = serializeSession(refresh_token, Date.now());
    const cookieStore = await cookies();
    const cookieOptions = getSessionCookieOptions(req);
    cookieStore.set("finfriend_session", sessionPayload, cookieOptions);

    return NextResponse.json({ ok: true, access_token: access_token || null });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Invalid payload";
    return NextResponse.json(
      {
        status: 400,
        code: "invalid_payload",
        message: msg,
      },
      { status: 400 }
    );
  }
}
