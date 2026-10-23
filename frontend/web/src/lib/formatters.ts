export function formatINR(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return "--";
  }
  const n = Number(amount);
  return `INR ${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPercent(ratio: number | string | null | undefined, decimals = 2): string {
  if (ratio === null || ratio === undefined || isNaN(Number(ratio))) {
    return "--";
  }
  const val = Number(ratio) * 100;
  return `${val.toFixed(decimals)}%`;
}

export function formatDecimal(val: number | string | null | undefined, decimals = 4): string {
  if (val === null || val === undefined || isNaN(Number(val))) {
    return "--";
  }
  return Number(val).toFixed(decimals);
}

export function formatBps(ratio: number | string | null | undefined): string {
  if (ratio === null || ratio === undefined || isNaN(Number(ratio))) {
    return "--";
  }
  return `${(Number(ratio) * 10000).toFixed(0)} bps`;
}

export function truncateString(str: string | null | undefined, maxLen = 80): string {
  if (!str) return "--";
  if (str.length <= maxLen) return str;
  return `${str.slice(0, maxLen - 3)}...`;
}

export function formatFiscalPeriod(raw?: string | null): string {
  if (!raw) return "";
  const trimmed = raw.trim();
  if (!trimmed) return "";

  if (/^annual\b/i.test(trimmed) || /^(?:full\s*year|12m|fy\s*\d{2,4})$/i.test(trimmed)) {
    return "Annual";
  }

  const canonicalMatch = trimmed.match(/^Q([1-4])\s+FY(\d{2})$/i);
  if (canonicalMatch) {
    return `Q${canonicalMatch[1]} FY${canonicalMatch[2]}`;
  }

  const quarterYearMatch = trimmed.match(/^Q([1-4])\s+(?:FY)?(\d{2,4})$/i);
  if (quarterYearMatch) {
    const q = quarterYearMatch[1];
    const yr = parseInt(quarterYearMatch[2], 10);
    const shortYr = yr > 99 ? yr % 100 : yr;
    return `Q${q} FY${String(shortYr).padStart(2, "0")}`;
  }

  const dashMatch = trimmed.match(/(?:(\d{4})-)?(\d{4})-Q([1-4])/i);
  if (dashMatch) {
    const q = dashMatch[3];
    const yr = parseInt(dashMatch[2], 10);
    const shortYr = yr % 100;
    return `Q${q} FY${String(shortYr).padStart(2, "0")}`;
  }

  return trimmed;
}
