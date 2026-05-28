// ─────────────────────────────────────────────────────────────────────────────
// REGIME TRANSITION ENGINE
//
// The most important system: we care less about "what regime are we in?" and
// more about "what is the probability of a regime transition?". The backend
// emits a fitted Hidden-Markov transition matrix; this engine turns it into
// forward-looking decision intelligence:
//
//   • persistence / transition probability of the current state
//   • ranked most-likely next regimes
//   • expected dwell (duration) in the current regime
//   • transition instability + a discrete stability rating
// ─────────────────────────────────────────────────────────────────────────────

import type { MarketPayload, RegimeTransitionPayload } from "@/types/market";
import type {
  RegimeTransitionEdge,
  StabilityLevel,
  TransitionState,
} from "@/engines/types";

const EMPTY: TransitionState = {
  current: "UNKNOWN",
  persistence: 0,
  nextRegimes: [],
  mostLikelyNext: null,
  expectedDurationBars: null,
  transitionProbability: 0,
  instability: 0,
  stability: "STABLE",
  lowConfidence: true,
  available: false,
};

function stabilityFrom(instability: number, persistence: number): StabilityLevel {
  if (instability >= 0.55 || persistence < 0.55) return "UNSTABLE";
  if (instability >= 0.3 || persistence < 0.75) return "FRAGILE";
  return "STABLE";
}

export function computeTransitionState(market: MarketPayload): TransitionState {
  const rt: RegimeTransitionPayload | undefined = market.regime_transition;
  if (!rt || !rt.matrix || !rt.states?.length) return EMPTY;

  const current =
    rt.current_state ?? market.hmm_regime ?? rt.states[0] ?? "UNKNOWN";

  const row = rt.matrix[current] ?? {};
  const persistence = clampNum(rt.persistence?.[current] ?? row[current] ?? 0);

  const nextRegimes: RegimeTransitionEdge[] = Object.entries(row)
    .filter(([to]) => to !== current)
    .map(([to, probability]) => ({ to, probability: clampNum(probability) }))
    .sort((a, b) => b.probability - a.probability);

  const transitionProbability = clampNum(1 - persistence);
  const mostLikelyNext = nextRegimes.length ? nextRegimes[0] : null;

  const expectedDurationBars =
    rt.expected_duration?.[current] != null
      ? rt.expected_duration[current]!
      : persistence > 0 && persistence < 1
        ? 1 / (1 - persistence)
        : null;

  const instability = clampNum(rt.instability_score);

  return {
    current,
    persistence,
    nextRegimes,
    mostLikelyNext,
    expectedDurationBars,
    transitionProbability,
    instability,
    stability: stabilityFrom(instability, persistence),
    lowConfidence: rt.low_confidence ?? false,
    available: true,
  };
}

function clampNum(x: number): number {
  if (x == null || Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}
