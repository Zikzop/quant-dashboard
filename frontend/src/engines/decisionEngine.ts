// ─────────────────────────────────────────────────────────────────────────────
// DECISION ENGINE — composition root
//
// Runs every sub-engine and fuses them into a single DecisionState that drives
// the Level-1 Primary Decision Layer. This is the only place where cross-engine
// trade-offs are resolved (e.g. a strong directional probability is suppressed
// by HTF conflict, crisis coupling, or extreme uncertainty).
// ─────────────────────────────────────────────────────────────────────────────

import type { MarketPayload, MTFAlignment } from "@/types/market";
import type {
  DecisionState,
  DirectionBias,
  EntryQualityRating,
} from "@/engines/types";
import { computeProbabilityState } from "@/engines/probability/probabilityEngine";
import { computeRiskState } from "@/engines/risk/riskEngine";
import { computeTransitionState } from "@/engines/transition/transitionEngine";
import { computeCorrelationState } from "@/engines/correlation/correlationEngine";
import { computeRegimeDecomposition } from "@/engines/regime/regimeEngine";
import { computeExecutionState } from "@/engines/execution/executionEngine";
import { computeUncertaintyState } from "@/engines/uncertainty/uncertaintyEngine";
import { computeCapitalAllocation } from "@/engines/capital/capitalAllocationEngine";
import { computeRegimeLifecycle } from "@/engines/regime/regimeLifecycleEngine";

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function ratingFromScore(score: number): EntryQualityRating {
  if (score >= 0.68) return "HIGH";
  if (score >= 0.5) return "ACCEPTABLE";
  if (score >= 0.32) return "LOW_EDGE";
  return "AVOID";
}

export function computeDecisionState(
  market: MarketPayload,
  alignment: MTFAlignment | null,
): DecisionState {
  const probability = computeProbabilityState(market);
  const risk = computeRiskState(market);
  const transition = computeTransitionState(market);
  const correlation = computeCorrelationState(market);
  const regime = computeRegimeDecomposition(market, probability);
  const execution = computeExecutionState(market);
  const uncertainty = computeUncertaintyState(market, probability, transition, risk);

  // ── Direction ───────────────────────────────────────────────────────────
  const bull = probability.bull.calibrated;
  let direction: DirectionBias = "NEUTRAL";
  if (bull >= 0.55) direction = "LONG";
  else if (bull <= 0.45) direction = "SHORT";
  // Mean-revert fade flips the directional read relative to the impulse.
  if (regime.executionBias === "FADE") {
    direction = regime.micro === "BULLISH_IMPULSE" ? "SHORT" : regime.micro === "BEARISH_IMPULSE" ? "LONG" : direction;
  }
  if (regime.executionBias === "NO_TRADE") direction = "NEUTRAL";

  const directionLabel =
    direction === "LONG" ? "LONG BIAS" : direction === "SHORT" ? "SHORT BIAS" : "NO DIRECTIONAL EDGE";

  // ── Alignment ───────────────────────────────────────────────────────────
  const alignmentRatio =
    alignment && alignment.total > 0 ? alignment.aligned_count / alignment.total : 0.5;
  const alignmentState = alignment?.state ?? "PARTIAL";

  // ── Entry quality (weighted, penalty-driven) ──────────────────────────────
  const convictionStrength = Math.abs(2 * bull - 1); // 0..1
  let entryScore =
    0.28 * convictionStrength +
    0.2 * alignmentRatio +
    0.18 * regime.coherence +
    0.18 * (1 - uncertainty.score) +
    0.16 * (1 - execution.executionRisk);

  // Cross-engine penalties.
  if (alignment?.htf_conflict_penalty) entryScore -= alignment.htf_conflict_penalty * 0.35;
  if (correlation.crisisCoupling) entryScore -= 0.12;
  if (risk.tailRisk === "EXTREME") entryScore -= 0.15;
  else if (risk.tailRisk === "FAT_TAILED") entryScore -= 0.06;
  if (transition.stability === "UNSTABLE") entryScore -= 0.1;
  if (regime.structural === "CRISIS") entryScore -= 0.25;

  entryScore = clamp01(entryScore);
  let entryQuality = ratingFromScore(entryScore);

  // ── Trade suppression ─────────────────────────────────────────────────────
  const suppressTrade =
    regime.executionBias === "NO_TRADE" ||
    regime.structural === "CRISIS" ||
    uncertainty.level === "EXTREME" ||
    entryQuality === "AVOID";

  if (suppressTrade && entryQuality !== "AVOID") entryQuality = "LOW_EDGE";

  // ── Headline priority warnings ─────────────────────────────────────────────
  const headline: string[] = [];
  if (regime.structural === "CRISIS") headline.push("CRISIS REGIME — CAPITAL PRESERVATION MODE");
  if (correlation.crisisCoupling) headline.push("CROSS-ASSET CRISIS COUPLING");
  if (risk.tailRisk === "EXTREME") headline.push("EXTREME TAIL RISK");
  if (alignment?.macro_micro_divergence) headline.push("MACRO / MICRO TIMEFRAME DIVERGENCE");
  if (transition.stability === "UNSTABLE") headline.push("REGIME TRANSITION UNSTABLE");
  if (execution.executionRisk > 0.6) headline.push("DEGRADED EXECUTION CONDITIONS");

  const base = {
    structuralRegime: regime.structural,
    microRegime: regime.micro,
    executionBias: regime.executionBias,
    direction,
    directionLabel,
    alignmentState,
    alignmentRatio,
    entryQuality,
    entryScore,
    riskState: market.market_state?.risk_state ?? "--",
    confidence: uncertainty.confidence,
    regimeStability: transition.stability,
    expectedEdgePct: uncertainty.expectedEdgePct,
    expectedDrawdownPct: uncertainty.expectedDrawdownPct,
    uncertaintyLevel: uncertainty.level,
    suppressTrade,
    headline,
    probability,
    uncertainty,
    regime,
    transition,
    correlation,
    execution,
    risk,
  };

  const capital = computeCapitalAllocation(base);
  const lifecycle = computeRegimeLifecycle(market, transition, regime.structural, regime.micro);

  return { ...base, capital, lifecycle };
}
