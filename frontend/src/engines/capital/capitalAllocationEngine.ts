// ─────────────────────────────────────────────────────────────────────────────
// CAPITAL ALLOCATION ENGINE
//
// Translates decision intelligence into deployable risk units. Risk-first:
// uncertainty, transition instability, vol regime, alignment, and historical
// edge jointly determine how much capital to commit.
// ─────────────────────────────────────────────────────────────────────────────

import type {
  CapitalAllocationState,
  DecisionState,
  RiskSizeRecommendation,
} from "@/engines/types";

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function sizeFromScore(score: number): RiskSizeRecommendation {
  if (score < 0.15) return "NO_TRADE";
  if (score < 0.35) return "QUARTER_R";
  if (score < 0.55) return "HALF_R";
  if (score < 0.75) return "THREE_QUARTER_R";
  return "FULL_SIZE";
}

function rFromRecommendation(rec: RiskSizeRecommendation): number {
  switch (rec) {
    case "NO_TRADE": return 0;
    case "QUARTER_R": return 0.25;
    case "HALF_R": return 0.5;
    case "THREE_QUARTER_R": return 0.75;
    case "FULL_SIZE": return 1;
  }
}

export function computeCapitalAllocation(
  decision: Omit<DecisionState, "capital" | "lifecycle">,
): CapitalAllocationState {
  const rationale: string[] = [];

  let score =
    0.28 * decision.entryScore +
    0.22 * decision.confidence +
    0.18 * decision.alignmentRatio +
    0.16 * (1 - decision.uncertainty.score) +
    0.16 * (1 - decision.transition.instability);

  if (decision.suppressTrade) {
    score *= 0.1;
    rationale.push("Trade suppressed — no executable edge");
  }
  if (decision.transition.stability === "UNSTABLE") {
    score -= 0.2;
    rationale.push("Regime transition unstable — reduce deployment");
  } else if (decision.transition.stability === "FRAGILE") {
    score -= 0.08;
    rationale.push("Fragile regime — conservative sizing");
  }
  if (decision.uncertainty.level === "EXTREME") {
    score -= 0.25;
    rationale.push("Extreme uncertainty — capital preservation");
  } else if (decision.uncertainty.level === "HIGH") {
    score -= 0.12;
    rationale.push("Elevated uncertainty — size down");
  }
  if (decision.risk.tailRisk === "EXTREME" || decision.risk.tailRisk === "FAT_TAILED") {
    score -= 0.15;
    rationale.push("Fat-tail risk — reduce exposure");
  }
  if (decision.correlation.crisisCoupling) {
    score -= 0.1;
    rationale.push("Cross-asset crisis coupling");
  }
  if (decision.execution.executionRisk > 0.6) {
    score -= 0.08;
    rationale.push("Degraded execution conditions");
  }

  score = clamp01(score);

  const recommendation = decision.suppressTrade && score < 0.2 ? "NO_TRADE" : sizeFromScore(score);
  const recommendedRiskR = rFromRecommendation(recommendation);
  const conviction = clamp01(decision.confidence * decision.entryScore);
  const exposureMultiplier = clamp01(score * (1 + decision.expectedEdgePct / 100));
  const riskBudgetUsagePct = recommendedRiskR * 100 * (1 + decision.risk.annualizedVol / 100);

  if (rationale.length === 0) {
    if (recommendation === "FULL_SIZE") rationale.push("Strong alignment, low uncertainty");
    else if (recommendation === "NO_TRADE") rationale.push("Insufficient edge for capital deployment");
    else rationale.push("Moderate conditions — scaled deployment");
  }

  return {
    recommendation,
    recommendedRiskR,
    recommendedSizePct: recommendedRiskR * 100,
    exposureMultiplier,
    conviction,
    riskBudgetUsagePct: Math.min(100, riskBudgetUsagePct),
    rationale,
  };
}
