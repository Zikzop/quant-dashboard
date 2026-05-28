"use client";

import { useMemo } from "react";
import type { MarketPayload } from "@/types/market";
import type { DecisionState } from "@/engines/types";
import { computeDecisionState } from "@/engines/decisionEngine";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

// Recomputes the full decision composition whenever the active market payload
// or the multi-timeframe alignment changes. Memoized so the (non-trivial)
// calibration fit only runs when inputs actually change.
export function useDecision(market: MarketPayload | null): DecisionState | null {
  const alignment = useTimeframeStore((s) => s.alignment);

  return useMemo(() => {
    if (!market || !market.chart_data?.length) return null;
    return computeDecisionState(market, alignment);
  }, [market, alignment]);
}
