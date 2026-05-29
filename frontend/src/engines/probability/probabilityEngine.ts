// ─────────────────────────────────────────────────────────────────────────────
// PROBABILITY ENGINE
//
// Converts the backend's raw regime/direction probabilities into *calibrated*,
// uncertainty-bounded estimates. The calibration map is fit in-sample against
// the asset's own realized outcomes (no look-ahead beyond the labeling horizon),
// then the current raw probability is passed through:
//
//   raw → isotonic(reliability) → Platt(logistic) → Bayesian shrink → bounded
//
// The result rarely exceeds realistic confidence because (a) isotonic maps onto
// observed hit-rates, (b) Platt corrects systematic over/under-confidence, and
// (c) Bayesian shrinkage pulls thin-evidence extremes toward the base rate.
// ─────────────────────────────────────────────────────────────────────────────

import type { ChartBar, MarketPayload } from "@/types/market";
import type {
  CalibratedProbability,
  ProbabilityState,
} from "@/engines/types";
import {
  applyIsotonic,
  applyPlatt,
  bayesianShrink,
  brierScore,
  clamp01,
  fitIsotonic,
  fitPlatt,
  reliabilityBins,
  wilsonInterval,
  type IsotonicModel,
  type PlattParams,
  type Sample,
} from "./calibration";

// Hard realism guard: directional conviction in markets effectively never
// justifies > ~92% over a short horizon. This bound is the last line of defense.
const MAX_CONFIDENCE = 0.92;
const MIN_SAMPLES = 24;

function probNorm(v?: number): number {
  if (v == null || Number.isNaN(v)) return 0.5;
  return v > 1 ? v / 100 : v;
}

interface CalibratorBundle {
  isotonic: IsotonicModel | null;
  platt: PlattParams;
  samples: Sample[];
  baseRate: number;
  method: ProbabilityState["diagnostics"]["method"];
}

function buildCalibrator(samples: Sample[]): CalibratorBundle {
  const baseRate =
    samples.length > 0
      ? clamp01(samples.reduce((a, s) => a + s.y, 0) / samples.length)
      : 0.5;

  if (samples.length < MIN_SAMPLES) {
    return { isotonic: null, platt: { A: 1, B: 0 }, samples, baseRate, method: "bayes-only" };
  }
  const isotonic = fitIsotonic(samples);
  const platt = fitPlatt(samples);
  return {
    isotonic,
    platt,
    samples,
    baseRate,
    method: isotonic ? "isotonic+platt+bayes" : "platt+bayes",
  };
}

function calibrate(
  raw: number,
  bundle: CalibratorBundle,
): CalibratedProbability {
  const r = clamp01(raw);
  const n = bundle.samples.length;

  let stage = r;
  if (bundle.isotonic) stage = applyIsotonic(stage, bundle.isotonic);
  if (n >= MIN_SAMPLES) stage = applyPlatt(stage, bundle.platt);

  // Bayesian shrink toward the empirical base rate. Evidence strength scales
  // with sample coverage; thin samples shrink hard toward the base rate.
  const strength = n >= MIN_SAMPLES ? 12 : 40;
  const evidenceN = Math.min(n, 80);
  let calibrated = bayesianShrink(stage, bundle.baseRate, strength, evidenceN);
  calibrated = Math.max(1 - MAX_CONFIDENCE, Math.min(MAX_CONFIDENCE, calibrated));

  const effN = Math.max(8, n);
  const ci = wilsonInterval(calibrated, effN);

  return {
    raw: r,
    calibrated,
    interval: { point: calibrated, lower: ci.lower, upper: ci.upper, n: effN },
    shrinkage: r - calibrated,
  };
}

// ── Outcome labeling from the chart's own history ───────────────────────────────
// We build separate calibration sets for each predicted probability so each map
// reflects the realized frequency of *that* event.

function buildSamples(
  bars: ChartBar[],
  horizon: number,
  predict: (b: ChartBar) => number | undefined,
  outcome: (cur: ChartBar, fut: ChartBar) => number,
): Sample[] {
  const out: Sample[] = [];
  for (let i = 0; i < bars.length - horizon; i++) {
    const p = predict(bars[i]);
    if (p == null || Number.isNaN(p)) continue;
    out.push({ p: clamp01(p > 1 ? p / 100 : p), y: outcome(bars[i], bars[i + horizon]) });
  }
  return out;
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

// Standard deviation of single-bar returns — used to scale the "crisis" label
// to a genuine tail move rather than a fixed (asset-inappropriate) percentage.
function returnStd(bars: ChartBar[]): number {
  const rets: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const prev = bars[i - 1].close;
    if (prev > 0) rets.push((bars[i].close - prev) / prev);
  }
  if (rets.length < 2) return 0.02;
  const m = rets.reduce((a, b) => a + b, 0) / rets.length;
  const v = rets.reduce((a, b) => a + (b - m) ** 2, 0) / (rets.length - 1);
  return Math.sqrt(v);
}

export function computeProbabilityState(market: MarketPayload): ProbabilityState {
  const bars = market.chart_data ?? [];
  const horizon = horizonForTimeframe(market.timeframe);

  // A "crisis" outcome is a genuine multi-sigma adverse move, defined relative
  // to the asset's own volatility (a −1.5% day is routine for BTC, not a crisis).
  const sigma = returnStd(bars);
  const crisisDrop = Math.max(0.02, 2.6 * sigma * Math.sqrt(horizon));

  // Directional (up) calibration: predicted via per-bar trend_probability
  // oriented by the bar's direction; realized by forward close change.
  const dirSamples = buildSamples(
    bars,
    horizon,
    (b) => {
      const tp = b.trend_probability;
      if (tp == null) return undefined;
      const up = (b.direction ?? "").toUpperCase().includes("BULL");
      const conv = tp > 1 ? tp / 100 : tp;
      return up ? 0.5 + 0.5 * conv : 0.5 - 0.5 * conv;
    },
    (cur, fut) => (fut.close > cur.close ? 1 : 0),
  );

  const trendSamples = buildSamples(
    bars,
    horizon,
    (b) => b.trend_probability,
    // "Trend realized" = price continued in the EMA-implied direction.
    (cur, fut) => {
      const dir = Math.sign((cur.ema20 ?? cur.close) - (cur.ema50 ?? cur.close));
      const move = Math.sign(fut.close - cur.close);
      return dir !== 0 && dir === move ? 1 : 0;
    },
  );

  const crisisSamples = buildSamples(
    bars,
    horizon,
    (b) => b.crisis_probability,
    // "Crisis realized" = a multi-sigma adverse move materialized.
    (cur, fut) => {
      if (cur.close <= 0) return 0;
      const ret = (fut.close - cur.close) / cur.close;
      return ret < -crisisDrop ? 1 : 0;
    },
  );

  const meanRevSamples = buildSamples(
    bars,
    horizon,
    (b) => b.mean_revert_probability,
    // "Mean reversion realized" = move opposed the prevailing EMA slope.
    (cur, fut) => {
      const dir = Math.sign((cur.ema20 ?? cur.close) - (cur.ema50 ?? cur.close));
      const move = Math.sign(fut.close - cur.close);
      return dir !== 0 && move !== 0 && dir !== move ? 1 : 0;
    },
  );

  const dirCal = buildCalibrator(dirSamples);
  const trendCal = buildCalibrator(trendSamples);
  const crisisCal = buildCalibrator(crisisSamples);
  const meanRevCal = buildCalibrator(meanRevSamples);

  // Current raw inputs.
  const rawBull = probNorm(market.bull_probability);
  const bull = calibrate(rawBull, dirCal);
  const bear = calibrate(1 - rawBull, dirCal);

  // Re-normalize bull/bear so they sum to 1 after independent calibration.
  const sumBB = bull.calibrated + bear.calibrated || 1;
  const bullNorm: CalibratedProbability = {
    ...bull,
    calibrated: bull.calibrated / sumBB,
    interval: { ...bull.interval, point: bull.calibrated / sumBB },
  };
  const bearNorm: CalibratedProbability = {
    ...bear,
    calibrated: bear.calibrated / sumBB,
    interval: { ...bear.interval, point: bear.calibrated / sumBB },
  };

  const trend = calibrate(probNorm(market.trend_probability), trendCal);
  const crisis = calibrate(probNorm(market.crisis_probability), crisisCal);
  const meanRevert = calibrate(probNorm(market.mean_revert_probability), meanRevCal);

  // Dispersion: normalized entropy across the {trend, meanRevert, crisis}
  // simplex — high entropy => indecisive regime mixture.
  const dispersion = simplexEntropy([
    trend.calibrated,
    meanRevert.calibrated,
    crisis.calibrated,
  ]);

  const brierRaw =
    dirCal.samples.length >= MIN_SAMPLES
      ? brierScore(dirCal.samples, (p) => p)
      : null;
  const brierCalibrated =
    dirCal.samples.length >= MIN_SAMPLES
      ? brierScore(dirCal.samples, (p) => {
          let s = p;
          if (dirCal.isotonic) s = applyIsotonic(s, dirCal.isotonic);
          s = applyPlatt(s, dirCal.platt);
          return s;
        })
      : null;

  return {
    bull: bullNorm,
    bear: bearNorm,
    trend,
    meanRevert,
    crisis,
    dispersion,
    diagnostics: {
      method: dirCal.method,
      sampleSize: dirCal.samples.length,
      horizonBars: horizon,
      brierRaw,
      brierCalibrated,
      reliability:
        dirCal.samples.length >= MIN_SAMPLES
          ? reliabilityBins(dirCal.samples, (p) => {
              let s = p;
              if (dirCal.isotonic) s = applyIsotonic(s, dirCal.isotonic);
              s = applyPlatt(s, dirCal.platt);
              return s;
            })
          : [],
      plattA: dirCal.platt.A,
      plattB: dirCal.platt.B,
    },
  };
}

function simplexEntropy(parts: number[]): number {
  const sum = parts.reduce((a, b) => a + Math.max(0, b), 0);
  if (sum <= 0) return 1;
  const probs = parts.map((p) => Math.max(1e-9, p) / sum);
  const h = -probs.reduce((a, p) => a + p * Math.log(p), 0);
  const hMax = Math.log(parts.length);
  return clamp01(h / (hMax || 1));
}
