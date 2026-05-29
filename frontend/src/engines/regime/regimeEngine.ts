// ─────────────────────────────────────────────────────────────────────────────
// REGIME DECOMPOSITION ENGINE
//
// The legacy system produced contradictions like "MEAN_REVERT + STRONG BUY".
// We resolve this by decomposing the market read into three orthogonal layers:
//
//   STRUCTURAL  — the macro regime (Trending / Mean-Revert / Volatile / Crisis /
//                 Recovery), driven by the HMM state + trend strength.
//   MICRO       — the short-horizon impulse (bullish/bearish impulse,
//                 compression, exhaustion), driven by ADX/DI + vol slope.
//   EXECUTION   — the actionable bias (long/short scalp, breakout, fade,
//                 no-trade), derived from the interaction of the two above.
//
// This prevents a structural mean-revert regime from emitting a trend-following
// "STRONG BUY"; instead it yields a coherent "FADE" execution bias.
// ─────────────────────────────────────────────────────────────────────────────

import type { MarketPayload } from "@/types/market";
import type {
  ExecutionBias,
  MicroRegime,
  ProbabilityState,
  RegimeDecomposition,
  StructuralRegime,
} from "@/engines/types";

function classifyStructural(market: MarketPayload, prob: ProbabilityState): StructuralRegime {
  const hmm = (market.hmm_regime ?? market.regime ?? "").toUpperCase();
  const vol = (market.vol_regime ?? market.market_state?.volatility_regime ?? "").toUpperCase();

  // Crisis is driven by the HMM regime label first; the calibrated crisis
  // probability only escalates when it is strongly elevated (avoids flagging
  // routine volatility as a crisis).
  if (hmm.includes("CRISIS") || prob.crisis.calibrated > 0.65) return "CRISIS";
  if (hmm.includes("RECOVER")) return "RECOVERY";
  if (hmm.includes("TREND")) return "TRENDING";
  if (hmm.includes("MEAN") || hmm.includes("REVERT") || hmm.includes("CHOP")) return "MEAN_REVERT";
  if (hmm.includes("VOLAT") || vol.includes("EXPAND")) return "VOLATILE";

  // Fall back to calibrated probabilities when the HMM label is ambiguous.
  if (prob.trend.calibrated >= prob.meanRevert.calibrated && prob.trend.calibrated > 0.45) return "TRENDING";
  if (prob.meanRevert.calibrated > 0.45) return "MEAN_REVERT";
  return "UNDEFINED";
}

function classifyMicro(market: MarketPayload): MicroRegime {
  const st = market.market_state;
  const adx = st?.adx ?? 0;
  const plusDi = st?.plus_di ?? 0;
  const minusDi = st?.minus_di ?? 0;
  const volSlope = market.vol_slope ?? 0;
  const dir = (st?.direction ?? "").toUpperCase();
  const volRegime = (market.vol_regime ?? "").toUpperCase();

  // Compression: low directional energy + contracting volatility.
  if (adx < 18 && (volRegime.includes("COMPRESS") || volRegime.includes("CONTRACT") || volSlope < 0)) {
    return "COMPRESSION";
  }
  // Exhaustion: strong prior trend (high ADX) but momentum rolling over.
  if (adx > 32 && volSlope < 0 && Math.abs(plusDi - minusDi) < 6) {
    return "EXHAUSTION";
  }
  if (adx >= 20 && (dir.includes("BULL") || plusDi > minusDi)) return "BULLISH_IMPULSE";
  if (adx >= 20 && (dir.includes("BEAR") || minusDi > plusDi)) return "BEARISH_IMPULSE";
  return "NEUTRAL";
}

function classifyExecutionBias(
  structural: StructuralRegime,
  micro: MicroRegime,
  prob: ProbabilityState,
): ExecutionBias {
  // Crisis / extreme uncertainty → stand down.
  if (structural === "CRISIS") return "NO_TRADE";

  if (structural === "TRENDING" || structural === "RECOVERY") {
    if (micro === "BULLISH_IMPULSE") return "LONG_SCALP";
    if (micro === "BEARISH_IMPULSE") return "SHORT_SCALP";
    if (micro === "COMPRESSION") return "BREAKOUT";
    if (micro === "EXHAUSTION") return "NO_TRADE";
    return prob.bull.calibrated > 0.5 ? "LONG_SCALP" : "SHORT_SCALP";
  }

  if (structural === "MEAN_REVERT") {
    // In a mean-revert regime, impulses are faded rather than followed.
    if (micro === "BULLISH_IMPULSE" || micro === "BEARISH_IMPULSE" || micro === "EXHAUSTION") return "FADE";
    if (micro === "COMPRESSION") return "NO_TRADE";
    return "FADE";
  }

  if (structural === "VOLATILE") {
    if (micro === "COMPRESSION") return "BREAKOUT";
    return "NO_TRADE";
  }

  return "NO_TRADE";
}

export function computeRegimeDecomposition(
  market: MarketPayload,
  prob: ProbabilityState,
): RegimeDecomposition {
  const structural = classifyStructural(market, prob);
  const micro = classifyMicro(market);
  const executionBias = classifyExecutionBias(structural, micro, prob);

  const rationale: string[] = [];
  rationale.push(`Structural HMM read: ${structural.replace(/_/g, " ")}`);
  rationale.push(`Micro impulse: ${micro.replace(/_/g, " ")} (ADX ${(market.market_state?.adx ?? 0).toFixed(0)})`);

  if (structural === "MEAN_REVERT" && (micro === "BULLISH_IMPULSE" || micro === "BEARISH_IMPULSE")) {
    rationale.push("Impulse inside a mean-revert regime → fade, do not chase");
  }
  if (structural === "TRENDING" && micro === "EXHAUSTION") {
    rationale.push("Trend exhaustion detected → momentum continuation suppressed");
  }
  if (executionBias === "BREAKOUT") {
    rationale.push("Volatility compression → positioned for expansion / breakout");
  }
  if (executionBias === "NO_TRADE") {
    rationale.push("No coherent edge — execution suppressed");
  }

  // Coherence: do structural + micro agree on direction?
  const microBull = micro === "BULLISH_IMPULSE";
  const microBear = micro === "BEARISH_IMPULSE";
  const trending = structural === "TRENDING" || structural === "RECOVERY";
  let coherence = 0.5;
  if (trending && (microBull || microBear)) coherence = 0.85;
  else if (structural === "MEAN_REVERT" && (microBull || microBear)) coherence = 0.7;
  else if (structural === "CRISIS") coherence = 0.3;
  else if (micro === "NEUTRAL") coherence = 0.45;

  return { structural, micro, executionBias, rationale, coherence };
}
