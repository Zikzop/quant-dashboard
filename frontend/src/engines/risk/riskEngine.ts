// ─────────────────────────────────────────────────────────────────────────────
// RISK ENGINE
//
// Estimates downside risk directly from the asset's realized per-bar return
// distribution rather than a Gaussian assumption (markets are fat-tailed).
//
//   • Historical VaR / CVaR (Expected Shortfall) at 95% and 99%
//   • Excess kurtosis + skew as explicit tail descriptors
//   • Regime-conditioned VaR (tail risk within the current HMM regime)
//   • Tail-exposure + volatility-instability warnings
// ─────────────────────────────────────────────────────────────────────────────

import type { ChartBar, MarketPayload } from "@/types/market";
import type { RiskState } from "@/engines/types";

function returnsFromBars(bars: ChartBar[]): number[] {
  const r: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const prev = bars[i - 1].close;
    const cur = bars[i].close;
    if (prev > 0 && cur > 0) r.push((cur - prev) / prev);
  }
  return r;
}

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0;
  const idx = (sorted.length - 1) * q;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

function annualizationFactor(tf?: string): number {
  // Bars per year, approximate, for crypto (24/7) — used for vol scaling.
  switch (tf) {
    case "1m": return 525600;
    case "5m": return 105120;
    case "15m": return 35040;
    case "1H": return 8760;
    case "4H": return 2190;
    default: return 365; // 1D
  }
}

const EMPTY: RiskState = {
  n: 0,
  var95: 0,
  var99: 0,
  cvar95: 0,
  cvar99: 0,
  expectedShortfall: 0,
  annualizedVol: 0,
  tailKurtosis: 0,
  skew: 0,
  tailRisk: "LOW",
  regimeConditionedVar95: 0,
  volInstability: false,
  warnings: [],
};

export function computeRiskState(market: MarketPayload): RiskState {
  const bars = market.chart_data ?? [];
  const returns = returnsFromBars(bars);
  if (returns.length < 20) return EMPTY;

  const n = returns.length;
  const mean = returns.reduce((a, b) => a + b, 0) / n;
  const variance =
    returns.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1);
  const std = Math.sqrt(variance);

  const sorted = [...returns].sort((a, b) => a - b);
  const var95 = quantile(sorted, 0.05);
  const var99 = quantile(sorted, 0.01);

  const tail95 = sorted.filter((r) => r <= var95);
  const tail99 = sorted.filter((r) => r <= var99);
  const cvar95 = tail95.length ? tail95.reduce((a, b) => a + b, 0) / tail95.length : var95;
  const cvar99 = tail99.length ? tail99.reduce((a, b) => a + b, 0) / tail99.length : var99;

  // Skew + excess kurtosis (Fisher).
  let m3 = 0;
  let m4 = 0;
  for (const r of returns) {
    const d = (r - mean) / (std || 1);
    m3 += d ** 3;
    m4 += d ** 4;
  }
  const skew = m3 / n;
  const excessKurtosis = m4 / n - 3;

  const annVol = std * Math.sqrt(annualizationFactor(market.timeframe)) * 100;

  // Regime-conditioned VaR: restrict the return sample to bars sharing the
  // current HMM regime.
  const currentRegime = (market.hmm_regime ?? "").toUpperCase();
  const regimeReturns: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const reg = (bars[i - 1].hmm_regime ?? "").toUpperCase();
    const prev = bars[i - 1].close;
    const cur = bars[i].close;
    if (reg && reg === currentRegime && prev > 0) {
      regimeReturns.push((cur - prev) / prev);
    }
  }
  const regimeConditionedVar95 =
    regimeReturns.length >= 15
      ? quantile([...regimeReturns].sort((a, b) => a - b), 0.05)
      : var95;

  // Tail classification — thresholds chosen so that normal (already volatile)
  // crypto/futures return distributions are not perpetually flagged EXTREME;
  // only genuinely heavy tails escalate.
  let tailRisk: RiskState["tailRisk"] = "LOW";
  if (excessKurtosis > 9 || cvar99 < -0.12) tailRisk = "EXTREME";
  else if (excessKurtosis > 4.5 || cvar99 < -0.08) tailRisk = "FAT_TAILED";
  else if (excessKurtosis > 2 || skew < -0.7) tailRisk = "ELEVATED";

  // Volatility instability: recent realized vol vs trailing baseline.
  const recent = returns.slice(-Math.min(20, n));
  const recentStd = stdOf(recent);
  const baseline = returns.slice(0, Math.max(1, n - recent.length));
  const baseStd = stdOf(baseline) || std;
  const volRatio = baseStd > 0 ? recentStd / baseStd : 1;
  const volInstability = volRatio > 1.6 || (market.vol_slope ?? 0) > 0.0008;

  const warnings: string[] = [];
  if (tailRisk === "EXTREME") warnings.push("EXTREME TAIL RISK — RETURN DISTRIBUTION HEAVILY FAT-TAILED");
  else if (tailRisk === "FAT_TAILED") warnings.push("FAT-TAILED DISTRIBUTION — GAUSSIAN SIZING UNDERSTATES RISK");
  if (skew < -0.8) warnings.push("STRONG NEGATIVE SKEW — CRASH-PRONE RETURN PROFILE");
  if (volInstability) warnings.push("VOLATILITY INSTABILITY — RECENT VOL EXPANSION DETECTED");
  if (regimeConditionedVar95 < var95 * 1.4) warnings.push("REGIME-CONDITIONED VaR EXCEEDS UNCONDITIONAL — ELEVATED REGIME RISK");

  return {
    n,
    var95: var95 * 100,
    var99: var99 * 100,
    cvar95: cvar95 * 100,
    cvar99: cvar99 * 100,
    expectedShortfall: cvar95 * 100,
    annualizedVol: annVol,
    tailKurtosis: excessKurtosis,
    skew,
    tailRisk,
    regimeConditionedVar95: regimeConditionedVar95 * 100,
    volInstability,
    warnings,
  };
}

function stdOf(arr: number[]): number {
  if (arr.length < 2) return 0;
  const m = arr.reduce((a, b) => a + b, 0) / arr.length;
  const v = arr.reduce((a, b) => a + (b - m) ** 2, 0) / (arr.length - 1);
  return Math.sqrt(v);
}
