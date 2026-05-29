// ─────────────────────────────────────────────────────────────────────────────
// REGIME LIFECYCLE ENGINE
//
// Answers "where are we inside the regime?" — more actionable than a static
// regime label. Uses dwell time, persistence, and micro-regime to classify
// lifecycle phase and estimate remaining regime life.
// ─────────────────────────────────────────────────────────────────────────────

import type { MarketPayload } from "@/types/market";
import type {
  RegimeLifecycleState,
  RegimePhase,
  StabilityLevel,
  TransitionState,
} from "@/engines/types";

function countRegimeAge(chartData: MarketPayload["chart_data"], current: string): number {
  if (!chartData?.length) return 0;
  let age = 0;
  for (let i = chartData.length - 1; i >= 0; i--) {
    const barRegime = chartData[i]?.hmm_regime ?? current;
    if (barRegime === current || !barRegime) age++;
    else break;
  }
  return age;
}

function inferPhase(
  structural: string,
  micro: string,
  ageBars: number,
  expectedDuration: number | null,
  persistence: number,
): RegimePhase {
  const s = structural.toUpperCase();
  const m = micro.toUpperCase();
  const lifecyclePct =
    expectedDuration != null && expectedDuration > 0
      ? ageBars / expectedDuration
      : persistence > 0.85
        ? Math.min(1, ageBars / 20)
        : Math.min(1, ageBars / 10);

  if (s.includes("CRISIS")) return "CRISIS_ENTRY";
  if (s.includes("RECOVERY")) return "RECOVERY";
  if (s.includes("MEAN")) {
    return lifecyclePct < 0.35 ? "EARLY_MEAN_REVERSION" : "LATE_MEAN_REVERSION";
  }
  if (m.includes("COMPRESSION")) return "COMPRESSION";
  if (m.includes("EXHAUSTION")) return "EXHAUSTION";
  if (s.includes("TREND") || s.includes("BULL") || s.includes("BEAR")) {
    if (lifecyclePct < 0.3) return "EARLY_TREND";
    if (lifecyclePct < 0.65) return "MID_TREND";
    if (lifecyclePct < 0.85) return "LATE_TREND";
    return "EXHAUSTION";
  }
  return "UNDEFINED";
}

const PHASE_LABELS: Record<RegimePhase, string> = {
  EARLY_TREND: "EARLY TREND",
  MID_TREND: "MID TREND",
  LATE_TREND: "LATE TREND",
  EXHAUSTION: "EXHAUSTION",
  EARLY_MEAN_REVERSION: "EARLY MEAN REVERSION",
  LATE_MEAN_REVERSION: "LATE MEAN REVERSION",
  COMPRESSION: "COMPRESSION",
  CRISIS_ENTRY: "CRISIS ENTRY",
  RECOVERY: "RECOVERY",
  UNDEFINED: "UNDEFINED",
};

export function computeRegimeLifecycle(
  market: MarketPayload,
  transition: TransitionState,
  structuralRegime: string,
  microRegime: string,
): RegimeLifecycleState {
  const current = transition.current !== "UNKNOWN"
    ? transition.current
    : market.hmm_regime ?? structuralRegime;

  const regimeAgeBars = countRegimeAge(market.chart_data, current);
  const expectedRemainingBars =
    transition.expectedDurationBars != null
      ? Math.max(0, transition.expectedDurationBars - regimeAgeBars)
      : null;

  const lifecyclePct =
    transition.expectedDurationBars != null && transition.expectedDurationBars > 0
      ? Math.min(1, regimeAgeBars / transition.expectedDurationBars)
      : transition.persistence > 0
        ? Math.min(1, regimeAgeBars / Math.max(1, 1 / (1 - transition.persistence)))
        : 0;

  const regimePhase = inferPhase(
    structuralRegime,
    microRegime,
    regimeAgeBars,
    transition.expectedDurationBars,
    transition.persistence,
  );

  const regimeStability: StabilityLevel = transition.stability;

  return {
    currentRegime: current,
    regimeAgeBars,
    regimePhase,
    expectedRemainingBars,
    regimeStability,
    lifecyclePct,
    phaseLabel: PHASE_LABELS[regimePhase],
  };
}
