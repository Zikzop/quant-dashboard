export function fmt(value?: number | null, dp = 2): string {
  if (value == null || Number.isNaN(value)) return "--";
  return value.toFixed(dp);
}

export function fmtPct(value?: number | null, dp = 1): string {
  if (value == null || Number.isNaN(value)) return "--";
  const v = Math.abs(value) < 1 ? value * 100 : value;
  return `${v.toFixed(dp)}%`;
}

export function fmtBps(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "--";
  return `${value.toFixed(1)}bps`;
}

export function fmtMs(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "--";
  return `${value.toFixed(0)}ms`;
}

export function fmtUsd(value?: number | null, dp = 2): string {
  if (value == null || Number.isNaN(value)) return "--";
  const abs = Math.abs(value);
  const prefix = value < 0 ? "-$" : "$";
  if (abs >= 1_000_000) return `${prefix}${(abs / 1_000_000).toFixed(dp)}M`;
  if (abs >= 1_000) return `${prefix}${(abs / 1_000).toFixed(dp)}K`;
  return `${prefix}${abs.toFixed(dp)}`;
}

export function fmtSign(value?: number | null, dp = 2): string {
  if (value == null || Number.isNaN(value)) return "--";
  return value > 0 ? `+${value.toFixed(dp)}` : value.toFixed(dp);
}

export function fmtTimestamp(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", { hour12: false });
}

export function probFraction(v?: number): number {
  if (v == null || Number.isNaN(v)) return 0;
  return v > 1 ? v / 100 : v;
}

export function finiteNum(value: number | undefined | null, fallback = 0): number {
  if (value == null || !Number.isFinite(value)) return fallback;
  return value;
}

export function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}
