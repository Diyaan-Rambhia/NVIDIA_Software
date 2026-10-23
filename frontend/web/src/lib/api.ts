import { parseApiError, ParsedApiError } from "./errors";

export class ApiError extends Error {
  status: number;
  parsed: ParsedApiError;
  rawPayload: unknown;

  constructor(status: number, parsed: ParsedApiError, rawPayload: unknown) {
    super(`HTTP ${status}: ${parsed.message}`);
    this.name = "ApiError";
    this.status = status;
    this.parsed = parsed;
    this.rawPayload = rawPayload;
  }
}

// Token holder exclusively in memory module scope for background/direct calls
let inMemoryToken: string | null = null;

export function setMemoryToken(token: string | null): void {
  inMemoryToken = token;
}

export function getMemoryToken(): string | null {
  return inMemoryToken;
}

export async function apiFetch<T = unknown>(
  endpoint: string,
  options: RequestInit = {},
  tokenOverride?: string | null
): Promise<T> {
  // Ensure the route is routed through local proxy prefix /backend
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const proxiedUrl = cleanEndpoint.startsWith("/backend/") ? cleanEndpoint : `/backend${cleanEndpoint}`;

  const headers = new Headers(options.headers || {});
  
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = tokenOverride !== undefined ? tokenOverride : inMemoryToken;
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(proxiedUrl, {
    ...options,
    headers,
  });

  let payload: unknown = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }
  } else {
    try {
      payload = await res.text();
    } catch {
      payload = null;
    }
  }

  if (!res.ok) {
    const parsed = parseApiError(res.status, payload);
    throw new ApiError(res.status, parsed, payload);
  }

  return payload as T;
}
