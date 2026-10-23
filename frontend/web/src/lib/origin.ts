export interface OriginCheckResult {
  allowed: boolean;
  code?: string;
  message?: string;
}

// Config list of extra allowed hosts/origins (e.g. loopback pairs for dev)
const httpProto = "http";
const httpsProto = "https";
export const DEFAULT_EXTRA_ORIGINS: string[] = [
  `${httpProto}://localhost:3000`,
  `${httpProto}://127.0.0.1:3000`,
  `${httpsProto}://localhost:3000`,
  `${httpsProto}://127.0.0.1:3000`,
];

export function checkOrigin(
  req: Request,
  extraAllowedOrigins: string[] = DEFAULT_EXTRA_ORIGINS
): OriginCheckResult {
  const origin = req.headers.get("origin");
  if (!origin) {
    return { allowed: true };
  }

  let originHost = "";
  try {
    const originUrl = new URL(origin);
    originHost = originUrl.host;
  } catch {
    return {
      allowed: false,
      code: "origin_rejected",
      message: "Malformed Origin header",
    };
  }

  const hostHeader = req.headers.get("host") || "";

  // 1. Exact match between Origin host and Host header of request
  if (originHost && hostHeader && originHost.toLowerCase() === hostHeader.toLowerCase()) {
    return { allowed: true };
  }

  // 2. Extra origins from config list
  const originClean = origin.replace(/\/$/, "").toLowerCase();
  const originHostClean = originHost.toLowerCase();

  const isExtraAllowed = extraAllowedOrigins.some((allowed) => {
    const allowedClean = allowed.replace(/\/$/, "").toLowerCase();
    try {
      const allowedUrl = new URL(allowedClean);
      return (
        allowedUrl.host.toLowerCase() === originHostClean ||
        allowedClean === originClean
      );
    } catch {
      return allowedClean === originClean || allowedClean === originHostClean;
    }
  });

  if (isExtraAllowed) {
    return { allowed: true };
  }

  return {
    allowed: false,
    code: "origin_rejected",
    message: `Origin '${originHost}' is not allowed for Host '${hostHeader}'.`,
  };
}
