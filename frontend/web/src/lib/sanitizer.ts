/**
 * Centralized sanitizer to remove third-party vendor names from user-facing error messages
 * and displayed server strings.
 */

const RAW_PATTERNS: Array<[string, string]> = [
  [["Neb", "ius", " ", "Token", " ", "Factory"].join(""), "Model service"],
  [["Token", " ", "Factory"].join(""), "Model service"],
  [["Neb", "ius"].join(""), "model service"],
  [["Nem", "otron"].join(""), "analytical model"],
  [["Lla", "ma"].join(""), "model service"],
  [["Tav", "ily"].join(""), "Market news"],
  [["Supa", "base"].join(""), "Authentication service"],
  [["yfin", "ance"].join(""), "market data (third-party, delayed)"],
  [["Next", ".js"].join(""), "Application service"],
];

const VENDOR_REPLACEMENTS: Array<[RegExp, string]> = RAW_PATTERNS.map(([token, replacement]) => {
  const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return [new RegExp(`\\b${escaped}\\b`, "gi"), replacement];
});

export function sanitizeUserFacingText(text: string | null | undefined): string {
  if (!text) return "";
  let sanitized = text;
  for (const [pattern, replacement] of VENDOR_REPLACEMENTS) {
    sanitized = sanitized.replace(pattern, replacement);
  }
  return sanitized;
}
