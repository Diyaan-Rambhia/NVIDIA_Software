#!/usr/bin/env node
import readline from "node:readline";
import { Writable } from "node:stream";

const baseUrl = process.argv[2] || process.env.BASE_URL || "http://localhost:3000";
const backendUrl = process.argv[3] || process.env.BACKEND_URL || "http://127.0.0.1:8000";

function prompt(query) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise((resolve) => {
    rl.question(query, (ans) => {
      rl.close();
      resolve(ans.trim());
    });
  });
}

function promptHidden(query) {
  let muted = false;
  const mutableStdout = new Writable({
    write(chunk, encoding, callback) {
      if (!muted) {
        process.stdout.write(chunk, encoding);
      }
      callback();
    },
  });

  const rl = readline.createInterface({
    input: process.stdin,
    output: mutableStdout,
    terminal: true,
  });

  return new Promise((resolve) => {
    process.stdout.write(query);
    muted = true;
    rl.question("", (password) => {
      process.stdout.write("\n");
      rl.close();
      resolve(password.trim());
    });
  });
}

async function run() {
  const email = await prompt("Email: ");
  const password = await promptHidden("Password: ");

  if (!email || !password) {
    console.log("Status: 400");
    console.log("Error code: missing_credentials");
    return;
  }

  // 1. Backend health check
  try {
    const healthRes = await fetch(`${backendUrl}/health`);
    console.log(`Backend health check status: ${healthRes.status}`);
  } catch {
    console.log("Backend health check status: 503");
    console.log("Backend health check error code: connection_failed");
  }

  // 2. Backend token endpoint
  let tokenData = null;
  try {
    const tokenRes = await fetch(`${backendUrl}/api/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    console.log(`Backend token endpoint status: ${tokenRes.status}`);
    tokenData = await tokenRes.json().catch(() => null);

    if (!tokenRes.ok) {
      const code =
        tokenData?.detail?.code ||
        tokenData?.error?.code ||
        tokenData?.code ||
        "auth_failed";
      console.log(`Backend token error code: ${code}`);
      return;
    }

    console.log(`has_access_token: ${Boolean(tokenData?.access_token)}`);
    console.log(`has_refresh_token: ${Boolean(tokenData?.refresh_token)}`);
    console.log(`has_expires_in: ${Boolean(tokenData?.expires_in)}`);
  } catch {
    console.log("Backend token endpoint status: 503");
    console.log("Backend token error code: connection_failed");
    return;
  }

  // 3. Next.js login route with Origin header matching BASE_URL
  let sessionCookiePair = "";
  try {
    const loginRes = await fetch(`${baseUrl}/api/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Origin: baseUrl,
      },
      body: JSON.stringify({
        access_token: tokenData.access_token,
        refresh_token: tokenData.refresh_token,
      }),
    });
    console.log(`Next.js login route status: ${loginRes.status}`);
    const loginBody = await loginRes.json().catch(() => null);

    if (!loginRes.ok) {
      console.log(`Next.js login error code: ${loginBody?.code || "login_rejected"}`);
      return;
    }

    const setCookie = loginRes.headers.get("set-cookie") || "";
    const isHttpOnly = /httponly/i.test(setCookie);
    const isSecure = /secure/i.test(setCookie);
    const sameSiteMatch = setCookie.match(/samesite=([^;]+)/i);
    const pathMatch = setCookie.match(/path=([^;]+)/i);

    console.log(`Cookie HttpOnly flag set: ${isHttpOnly}`);
    console.log(`Cookie Secure flag set: ${isSecure}`);
    console.log(`Cookie SameSite attribute: ${sameSiteMatch ? sameSiteMatch[1] : "not_set"}`);
    console.log(`Cookie Path attribute: ${pathMatch ? pathMatch[1] : "not_set"}`);

    sessionCookiePair = setCookie.split(";")[0];
  } catch {
    console.log("Next.js login route status: 503");
    console.log("Next.js login error code: connection_failed");
    return;
  }

  // 4. Next.js session route with returned cookie
  try {
    const sessionRes = await fetch(`${baseUrl}/api/auth/session`, {
      method: "POST",
      headers: {
        Cookie: sessionCookiePair,
        Origin: baseUrl,
      },
    });
    console.log(`Next.js session route status: ${sessionRes.status}`);
    const sessionBody = await sessionRes.json().catch(() => null);

    if (!sessionRes.ok) {
      console.log(`Next.js session error code: ${sessionBody?.code || "session_rejected"}`);
      return;
    }

    console.log(`Session check ok: true`);
  } catch {
    console.log("Next.js session route status: 503");
    console.log("Next.js session error code: connection_failed");
  }
}

run();
