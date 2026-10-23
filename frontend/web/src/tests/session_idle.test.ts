import { describe, it, expect } from "vitest";
import {
  serializeSession,
  parseSession,
  isSessionIdleTimedOut,
  sessionAfterRefresh,
  sessionAfterUserAction,
} from "@/lib/session_cookie";
import { SESSION_IDLE_HOURS } from "@/config/session";

describe("Session Idle Timeout and Refresh Constraints", () => {
  it("verifies SESSION_IDLE_HOURS config is 5", () => {
    expect(SESSION_IDLE_HOURS).toBe(5);
  });

  it("stays signed in at 4 hours 59 minutes of inactivity", () => {
    // Hand-written timestamps
    const baseTime = 1770000000000;
    const fourHoursFiftyNineMinutesLater = baseTime + (4 * 60 + 59) * 60 * 1000;

    const cookie = serializeSession("mock_refresh_token_abc", baseTime);
    const session = parseSession(cookie);
    expect(session).not.toBeNull();
    expect(session?.last_activity).toBe(baseTime);

    // 4h59m must not be timed out
    const timedOut = isSessionIdleTimedOut(session!.last_activity, fourHoursFiftyNineMinutesLater);
    expect(timedOut).toBe(false);
  });

  it("is signed out at 5 hours 1 minute of inactivity", () => {
    // Hand-written timestamps
    const baseTime = 1770000000000;
    const fiveHoursOneMinuteLater = baseTime + (5 * 60 + 1) * 60 * 1000;

    const cookie = serializeSession("mock_refresh_token_abc", baseTime);
    const session = parseSession(cookie);
    expect(session).not.toBeNull();

    // 5h01m must be timed out
    const timedOut = isSessionIdleTimedOut(session!.last_activity, fiveHoursOneMinuteLater);
    expect(timedOut).toBe(true);
  });

  it("background refresh does NOT extend the idle time", () => {
    const baseActivityTime = 1770000000000;
    const backgroundRefreshTime = baseActivityTime + 2 * 60 * 60 * 1000; // 2 hours later

    const initialCookie = serializeSession("refresh_token_1", baseActivityTime);

    // Background refresh gets a new refresh token
    const refreshedCookie = sessionAfterRefresh(initialCookie, "refresh_token_2");
    const sessionAfter = parseSession(refreshedCookie);

    expect(sessionAfter?.refresh_token).toBe("refresh_token_2");
    // last_activity must remain unchanged at baseActivityTime
    expect(sessionAfter?.last_activity).toBe(baseActivityTime);

    // At 5h01m from the base activity time, it must still be timed out despite the refresh
    const fiveHoursOneMinuteLater = baseActivityTime + (5 * 60 + 1) * 60 * 1000;
    expect(isSessionIdleTimedOut(sessionAfter!.last_activity, fiveHoursOneMinuteLater)).toBe(true);
  });

  it("deliberate user action updates last_activity", () => {
    const baseTime = 1770000000000;
    const userActionTime = baseTime + 30 * 60 * 1000; // 30 mins later

    const cookie = serializeSession("refresh_token_1", baseTime);
    const updatedCookie = sessionAfterUserAction(cookie, userActionTime);
    const session = parseSession(updatedCookie);

    expect(session?.refresh_token).toBe("refresh_token_1");
    expect(session?.last_activity).toBe(userActionTime);
  });
});
