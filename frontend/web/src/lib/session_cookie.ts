import { SESSION_IDLE_HOURS } from "@/config/session";

export interface SessionData {
  refresh_token: string;
  last_activity: number;
}

export function serializeSession(refreshToken: string, lastActivity: number): string {
  return Buffer.from(
    JSON.stringify({
      refresh_token: refreshToken,
      last_activity: lastActivity,
    })
  ).toString("base64");
}

export function parseSession(cookieValue: string | null | undefined): SessionData | null {
  if (!cookieValue) return null;
  try {
    const raw = Buffer.from(cookieValue, "base64").toString("utf-8");
    const parsed = JSON.parse(raw);
    if (typeof parsed.refresh_token === "string" && typeof parsed.last_activity === "number") {
      return {
        refresh_token: parsed.refresh_token,
        last_activity: parsed.last_activity,
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function isSessionIdleTimedOut(
  lastActivity: number,
  currentTime: number = Date.now(),
  maxHours: number = SESSION_IDLE_HOURS
): boolean {
  const maxIdleMs = maxHours * 60 * 60 * 1000;
  return currentTime - lastActivity > maxIdleMs;
}

export function sessionAfterRefresh(
  currentCookie: string,
  newRefreshToken: string
): string {
  const data = parseSession(currentCookie);
  const lastActivity = data ? data.last_activity : Date.now();
  // Preserves existing last_activity timestamp: background refresh must not extend idle time
  return serializeSession(newRefreshToken, lastActivity);
}

export function sessionAfterUserAction(
  currentCookie: string,
  currentTime: number = Date.now()
): string {
  const data = parseSession(currentCookie);
  if (!data) return "";
  return serializeSession(data.refresh_token, currentTime);
}

export function isRequestSecure(req: Request): boolean {
  if (process.env.NODE_ENV === "production") return true;
  const proto = req.headers.get("x-forwarded-proto");
  if (proto && proto.toLowerCase() === "https") return true;
  try {
    const parsed = new URL(req.url);
    if (parsed.protocol === "https:") return true;
  } catch {
    // fallback
  }
  return false;
}

export function getSessionCookieOptions(req: Request) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isRequestSecure(req),
    path: "/api/auth",
    maxAge: 30 * 24 * 60 * 60,
  };
}

export function getClearSessionCookieOptions(req: Request) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isRequestSecure(req),
    path: "/api/auth",
    maxAge: 0,
  };
}
