// ─────────────────────────────────────────────────────────────────────────────
// UNCERTAINTY ENGINE
//
// Replaces simplistic verdicts ("STRONG BUY") with an honest, quantified read:
//
//   Expected Edge:    +0.21%
//   Confidence:       73%
//   Regime Stability: LOW
//
// It fuses three independent uncertainty sources into one composite score:
//   1. Probabilistic dispersion (entropy of the regime simplex)
//   2. Regime instability (HMM transition engine)
//   3. Estimation uncertainty (width of the calibrated confidence interval)
//
// Expected edge is derived from the calibrated directional probability and the
// asset's realized per-horizon move; expected drawdown from the tail (CVaR).
// ─────────────────────────────────────────────────────────────────────────────

import type { ChartBar, MarketPayload } from "@/types/market";
import type {
  ProbabilityState,
  RiskState,
  TransitionState,
  UncertaintyLevel,
  UncertaintyState,
} from "@/engines/types";

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function horizonForTimeframe(tf?: string): number {
  switch (tf) {
    case "1m":
    case "5m":
      return 5;
    case "15m":
    case "1H":
      return 4;
    case "4H":
      return 3;
    default:
      return 3;
  }
}

// Expected absolute move over the decision horizon, in % of price.
function expectedMovePct(bars: ChartBar[], horizon: number): number {
  const slice = bars.slice(-30);
  if (slice.length < 2) return 0;
  const rets: number[] = [];
  for (let i = 1; i < slice.length; i++) {
    const prev = slice[i - 1].close;
    if (prev > 0) rets.push(Math.abs((slice[i].close - prev) / prev));
  }
  if (!rets.length) return 0;
  const avgAbs = rets.reduce((a, b) => a + b, 0) / rets.length;
  // Scale single-bar move to the horizon under a random-walk assumption.
  return avgAbs * Math.sqrt(horizon) * 100;
}

function levelFromScore(score: number): UncertaintyLevel {
  if (score >= 0.72) return "EXTREME";
  if (score >= 0.5) return "HIGH";
  if (score >= 0.3) return "MODERATE";
  return "LOW";
}

export function computeUncertaintyState(
  market: MarketPayload,
  prob: ProbabilityState,
  transition: TransitionState,
  risk: RiskState,
): UncertaintyState {
  const horizon = horizonForTimeframe(market.timeframe);
  const bars = market.chart_data ?? [];

  const dispersion = prob.dispersion;
  const regimeInstability = transition.available ? transition.instability : 0.4;
  const intervalWidth = clamp01(
    prob.bull.interval.upper - prob.bull.interval.lower,
  );

  // Low-evidence penalty: small calibration samples => more uncertainty.
  const samplePenalty = clamp01(1 - prob.diagnostics.sampleSize / 80) * 0.4;

  const score = clamp01(
    0.32 * dispersion +
      0.3 * regimeInstability +
      0.23 * Math.min(1, intervalWidth / 0.5) +
      0.15 * samplePenalty,
  );

  const level = levelFromScore(score);

  // Expected edge: calibrated directional conviction × expected move.
  const move = expectedMovePct(bars, horizon);
  const directionalConviction = 2 * prob.bull.calibrated - 1; // −1..1
  // Discount edge by execution-agnostic uncertainty.
  const expectedEdgePct = directionalConviction * move * (1 - 0.4 * score);

  // Expected drawdown: tail expectation, widened when regime is unstable.
  const baseTail = risk.cvar95 !== 0 ? risk.cvar95 : risk.var95;
  const expectedDrawdownPct = baseTail * (1 + 0.5 * regimeInstability);

  // Net confidence: directional conviction strength, discounted by uncertainty.
  const convictionStrength = Math.abs(directionalConviction); // 0..1
  const confidence = clamp01(convictionStrength * (1 - score) + 0.12 * (1 - score));

  return {
    level,
    score,
    dispersion,
    regimeInstability,
    intervalWidth,
    expectedEdgePct,
    expectedDrawdownPct,
    confidence,
  };
}
