import { describe, it, expect, beforeEach } from "vitest";
import { setMemoryToken, getMemoryToken } from "@/lib/api";

describe("In-memory token security", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it("stores token strictly in JavaScript memory", () => {
    const sampleToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test";
    setMemoryToken(sampleToken);

    expect(getMemoryToken()).toBe(sampleToken);
    expect(localStorage.getItem("token")).toBeNull();
    expect(sessionStorage.getItem("token")).toBeNull();
    expect(document.cookie).not.toContain(sampleToken);
  });

  it("clears memory token on logout without touching web storage", () => {
    setMemoryToken("active_token");
    setMemoryToken(null);

    expect(getMemoryToken()).toBeNull();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
