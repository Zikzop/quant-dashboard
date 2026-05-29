// ─────────────────────────────────────────────────────────────────────────────
// OPPORTUNITY RANKING ENGINE
//
// Cross-sectional ranking of the institutional universe. Each asset is scored
// on edge, transition risk, alignment, expected drawdown, and uncertainty.
// ─────────────────────────────────────────────────────────────────────────────

import type { MarketPayload } from "@/types/market";
import type { DecisionState, OpportunityRankEntry, OpportunityRankingState } from "@/engines/types";
import { ASSET_IDS } from "@/lib/assets/registry";

export interface AssetDecisionInput {
  assetId: string;
  market: MarketPayload | null;
  decision: DecisionState | null;
}

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function scoreAsset(
  decision: DecisionState | null,
  market: MarketPayload | null,
): Omit<OpportunityRankEntry, "rank" | "assetId"> {
  if (!decision || !market) {
    return {
      edgeScore: 0,
      transitionRisk: 1,
      alignmentScore: 0,
      expectedDrawdownPct: 0,
      uncertaintyScore: 1,
      compositeScore: 0,
      actionable: false,
    };
  }

  const edgeScore = clamp01(Math.abs(decision.expectedEdgePct) / 5 + decision.entryScore * 0.5);
  const transitionRisk = clamp01(decision.transition.instability + (1 - decision.transition.persistence) * 0.5);
  const alignmentScore = decision.alignmentRatio;
  const expectedDrawdownPct = Math.abs(decision.expectedDrawdownPct);
  const uncertaintyScore = decision.uncertainty.score;

  const compositeScore = clamp01(
    0.32 * edgeScore +
    0.22 * alignmentScore +
    0.18 * (1 - transitionRisk) +
    0.16 * (1 - uncertaintyScore) +
    0.12 * (1 - Math.min(1, expectedDrawdownPct / 10)) -
    (decision.suppressTrade ? 0.3 : 0),
  );

  return {
    edgeScore,
    transitionRisk,
    alignmentScore,
    expectedDrawdownPct,
    uncertaintyScore,
    compositeScore,
    actionable: !decision.suppressTrade && compositeScore > 0.25,
  };
}

export function rankOpportunities(
  inputs: AssetDecisionInput[],
  focusAsset: string,
): OpportunityRankingState {
  const scored: OpportunityRankEntry[] = inputs
    .map(({ assetId, decision, market }) => ({
      assetId,
      rank: 0,
      ...scoreAsset(decision, market),
    }))
    .sort((a, b) => b.compositeScore - a.compositeScore)
    .map((entry, i) => ({ ...entry, rank: i + 1 }));

  return {
    ranked: scored,
    best: scored[0] ?? null,
    focusAsset,
  };
}

export function buildRankingInputs(
  activeAsset: string,
  activeMarket: MarketPayload,
  activeDecision: DecisionState,
  otherAssets: Array<{ assetId: string; market: MarketPayload | null; decision: DecisionState | null }>,
): AssetDecisionInput[] {
  const others = new Map(otherAssets.map((a) => [a.assetId, a]));
  return ASSET_IDS.map((assetId) => {
    if (assetId === activeAsset) {
      return { assetId, market: activeMarket, decision: activeDecision };
    }
    const o = others.get(assetId);
    return { assetId, market: o?.market ?? null, decision: o?.decision ?? null };
  });
}
