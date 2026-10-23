import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getClearSessionCookieOptions } from "@/lib/session_cookie";
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
  cookieStore.set(
    "finfriend_session",
    "",
    getClearSessionCookieOptions(req)
  );

  return NextResponse.json({ ok: true });
}
