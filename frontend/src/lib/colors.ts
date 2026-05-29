export const C = {
  bg: "#080809",
  bg2: "#0a0a0c",
  surface: "#0d0d0f",
  surface2: "#111114",
  border: "#1c1c20",
  borderMid: "#26262c",
  borderHi: "#34343c",

  t1: "#f0f0f2",
  t2: "#a8a8b4",
  t3: "#6e6e7a",
  t4: "#4a4a56",

  bullish: "#22c55e",
  bullishDim: "rgba(34,197,94,0.15)",
  bearish: "#ef4444",
  bearishDim: "rgba(239,68,68,0.15)",
  volatile: "#f59e0b",
  volatileDim: "rgba(245,158,11,0.15)",
  crisis: "#ef4444",
  neutral: "#6b7280",
  safe: "#22c55e",
  warning: "#f59e0b",
  danger: "#ef4444",
  critical: "#dc2626",

  cyan: "#06b6d4",
  cyanDim: "rgba(6,182,212,0.15)",
  blue: "#3b82f6",
  blueDim: "rgba(59,130,246,0.15)",
  purple: "#a78bfa",
  purpleDim: "rgba(167,139,250,0.15)",
  amber: "#f59e0b",
  amberDim: "rgba(245,158,11,0.15)",

  candleUp: "#22c55e",
  candleDown: "#ef4444",
  ema20: "#06b6d4",
  ema50: "#3b82f6",
} as const;

export function statusColor(
  status: "SAFE" | "WARNING" | "DANGER" | "CRITICAL" | string
): string {
  switch (status) {
    case "SAFE": return C.safe;
    case "WARNING": return C.warning;
    case "DANGER": return C.danger;
    case "CRITICAL": return C.critical;
    default: return C.neutral;
  }
}

export function pnlColor(value: number): string {
  if (value > 0) return C.bullish;
  if (value < 0) return C.bearish;
  return C.t2;
}

export function proximityColor(pct: number): string {
  if (pct >= 80) return C.critical;
  if (pct >= 60) return C.danger;
  if (pct >= 40) return C.warning;
  return C.safe;
}

export function regimeColor(regime?: string): string {
  if (!regime) return C.neutral;
  const r = regime.toUpperCase();
  if (r.includes("BULLISH") || r.includes("TREND")) return C.bullish;
  if (r.includes("BEARISH")) return C.bearish;
  if (r.includes("CRISIS")) return C.crisis;
  if (r.includes("MEAN") || r.includes("CHOPPY")) return C.cyan;
  if (r.includes("VOLAT") || r.includes("EXPAND")) return C.volatile;
  if (r.includes("COMPRESS") || r.includes("CONTRACT")) return C.cyan;
  return C.neutral;
}
