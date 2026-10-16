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
