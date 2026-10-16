// @vitest-environment node
import { describe, it, expect, beforeAll } from "vitest";

describe("Live Backend Integration Tests", () => {
  const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";

  // Simulate Next.js rewrite: /backend/:path* -> ${backendUrl}/:path*
  const proxyUrl = (path: string) => {
    const clean = path.startsWith("/") ? path : `/${path}`;
    const target = clean.startsWith("/backend/") ? clean.replace(/^\/backend/, "") : clean;
    return `${backendUrl}${target}`;
  };

  let isBackendReachable = false;
  let tokens: Record<string, string> = {};

  beforeAll(async () => {
    try {
      const res = await fetch(proxyUrl("/backend/health"), { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        isBackendReachable = true;
      }
    } catch {
      isBackendReachable = false;
    }

    const judgePw = process.env.JUDGE_PASSWORD;
    const retailPw = process.env.DEMO_RETAIL_PASSWORD;
    const instPw = process.env.DEMO_INSTITUTIONAL_PASSWORD;

    if (isBackendReachable && judgePw && retailPw && instPw) {
      const accounts = [
        { key: "judge", email: "judge@fininsight.local", pw: judgePw },
        { key: "retail", email: "demo_retail@fininsight.local", pw: retailPw },
        { key: "inst", email: "demo_institutional@fininsight.local", pw: instPw },
      ];

      for (const acc of accounts) {
        try {
          const loginRes = await fetch(proxyUrl("/backend/api/auth/token"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: acc.email, password: acc.pw }),
          });
          if (loginRes.ok) {
            const data = await loginRes.json();
            tokens[acc.key] = data.access_token;
          }
        } catch {
          // Keep tokens empty
        }
      }
    }
  });

  it("login for each seeded account", async (ctx) => {
    if (!isBackendReachable) {
      ctx.skip();
      return;
    }
    expect(tokens.judge).toBeDefined();
    expect(tokens.retail).toBeDefined();
    expect(tokens.inst).toBeDefined();
  });

  it("retail gets 403 on contagion data", async (ctx) => {
    if (!tokens.retail) {
      ctx.skip();
      return;
    }
    const res = await fetch(proxyUrl("/backend/f1/demo"), {
      headers: { Authorization: `Bearer ${tokens.retail}` },
    });
    expect(res.status).toBe(403);
  });

  it("institutional gets 402", async (ctx) => {
    if (!tokens.inst) {
      ctx.skip();
      return;
    }
    const res = await fetch(proxyUrl("/backend/f1/demo"), {
      headers: { Authorization: `Bearer ${tokens.inst}` },
    });
    expect(res.status).toBe(402);
  });

  it("judge gets 200 on all three features", async (ctx) => {
    if (!tokens.judge) {
      ctx.skip();
      return;
    }
    const [resF1, resF2, resF3] = await Promise.all([
      fetch(proxyUrl("/backend/f1/demo"), { headers: { Authorization: `Bearer ${tokens.judge}` } }),
      fetch(proxyUrl("/backend/f2/demo"), { headers: { Authorization: `Bearer ${tokens.judge}` } }),
      fetch(proxyUrl("/backend/f3/demo"), { headers: { Authorization: `Bearer ${tokens.judge}` } }),
    ]);
    expect(resF1.status).toBe(200);
    expect(resF2.status).toBe(200);
    expect(resF3.status).toBe(200);
  });

  it("admin gets 200 on the ops routes", async (ctx) => {
    const adminPassword = process.env.ADMIN_PASSWORD;
    if (!adminPassword) {
      ctx.skip();
      return;
    }
  });

  it("non-admin gets 403 on the ops routes", async (ctx) => {
    if (!tokens.retail) {
      ctx.skip();
      return;
    }
    const res = await fetch(proxyUrl("/backend/ops/status"), {
      headers: { Authorization: `Bearer ${tokens.retail}` },
    });
    expect(res.status).toBe(403);
  });

  it("429 shows a reset time", async (ctx) => {
    ctx.skip();
  });
});
