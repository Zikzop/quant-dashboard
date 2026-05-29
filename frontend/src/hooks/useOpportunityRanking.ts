"use client";

import { useEffect, useMemo, useState } from "react";
import type { MarketPayload } from "@/types/market";
import type { DecisionState, OpportunityRankingState } from "@/engines/types";
import { computeDecisionState } from "@/engines/decisionEngine";
import { buildRankingInputs, rankOpportunities } from "@/engines/opportunity/opportunityRankingEngine";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { ASSET_IDS } from "@/lib/assets/registry";
import { fetchMarketTimeframe } from "@/lib/api";

function pseudoDecisionFromHeatmap(
  assetId: string,
  market: MarketPayload,
): DecisionState | null {
  const cell = market.correlation?.heatmap_cells?.find(
    (c) => c.asset.toUpperCase() === assetId || c.asset.includes(assetId),
  );
  if (!cell) return null;

  const ret = cell.daily_return_pct ?? 0;
  const z = cell.correlation_zscore_vs_btc ?? 0;
  const edge = Math.abs(ret) / 3 + Math.max(0, -z) * 0.05;

  const partial = computeDecisionState(market, null);
  return {
    ...partial,
    expectedEdgePct: edge,
    entryScore: Math.min(1, Math.abs(ret) / 2),
    alignmentRatio: 0.5,
    suppressTrade: Math.abs(ret) < 0.1,
    uncertainty: { ...partial.uncertainty, score: 0.5 + Math.abs(z) * 0.1 },
    transition: { ...partial.transition, instability: Math.abs(z) * 0.15 },
  };
}

export function useOpportunityRanking(
  market: MarketPayload | null,
  decision: DecisionState | null,
): OpportunityRankingState | null {
  const activeAsset = useTimeframeStore((s) => s.activeAsset);
  const activeRange = useTimeframeStore((s) => s.activeRange);
  const [snapshots, setSnapshots] = useState<Record<string, MarketPayload>>({});

  useEffect(() => {
    if (!market) return;
    let cancelled = false;

    const others = ASSET_IDS.filter((id) => id !== activeAsset);
    Promise.all(
      others.map((assetId) =>
        fetchMarketTimeframe("1D", assetId, activeRange)
          .then((data) => ({ assetId, data }))
          .catch(() => ({ assetId, data: null })),
      ),
    ).then((results) => {
      if (cancelled) return;
      const next: Record<string, MarketPayload> = {};
      for (const { assetId, data } of results) {
        if (data) next[assetId] = data;
      }
      setSnapshots(next);
    });

    return () => { cancelled = true; };
  }, [activeAsset, activeRange, market?.symbol]);

  return useMemo(() => {
    if (!market || !decision) return null;

    const otherAssets = ASSET_IDS.filter((id) => id !== activeAsset).map((assetId) => {
      const payload = snapshots[assetId] ?? null;
      let d: DecisionState | null = null;
      if (payload?.chart_data?.length) {
        d = computeDecisionState(payload, null);
      } else if (market.correlation?.heatmap_cells?.length) {
        d = pseudoDecisionFromHeatmap(assetId, market);
      }
      return { assetId, market: payload, decision: d };
    });

    const inputs = buildRankingInputs(activeAsset, market, decision, otherAssets);
    return rankOpportunities(inputs, activeAsset);
  }, [market, decision, activeAsset, snapshots]);
}
