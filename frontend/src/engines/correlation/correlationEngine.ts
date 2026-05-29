// ─────────────────────────────────────────────────────────────────────────────
// CROSS-ASSET CORRELATION ENGINE
//
// Consumes the backend rolling-correlation payload (ES / NQ / GOLD / DXY / BTC)
// and classifies the *correlation regime* rather than reporting static Pearson:
//
//   • mean absolute pairwise correlation across the basket
//   • crisis-coupling detection (broad correlations collapsing toward 1)
//   • covariance instability + regime-sensitive correlation shift
//
// This surfaces the diversification-decay risk that static correlation hides.
// ─────────────────────────────────────────────────────────────────────────────

import type { CorrelationPayload, MarketPayload } from "@/types/market";
import type { CorrelationRegime, CorrelationState } from "@/engines/types";

const EMPTY: CorrelationState = {
  available: false,
  regime: "NORMAL",
  meanAbsCorrelation: 0,
  meanCorrelation: 0,
  instability: 0,
  instabilityRegime: "--",
  crisisCoupling: false,
  strongestPair: null,
  shiftSensitivity: "--",
  shiftMagnitude: 0,
  warnings: [],
};

export function computeCorrelationState(market: MarketPayload): CorrelationState {
  const corr: CorrelationPayload | undefined = market.correlation;
  if (!corr?.matrix_labels?.length || !corr.matrix_values?.length) return EMPTY;

  const labels = corr.matrix_labels;
  const matrix = corr.matrix_values;

  let sumAbs = 0;
  let sumSigned = 0;
  let count = 0;
  let strongest: { pair: string; value: number } | null = null;

  for (let i = 0; i < labels.length; i++) {
    for (let j = i + 1; j < labels.length; j++) {
      const v = matrix[i]?.[j];
      if (v == null || Number.isNaN(v)) continue;
      sumAbs += Math.abs(v);
      sumSigned += v;
      count += 1;
      if (!strongest || Math.abs(v) > Math.abs(strongest.value)) {
        strongest = { pair: `${labels[i]}/${labels[j]}`, value: v };
      }
    }
  }

  const meanAbs = count ? sumAbs / count : 0;
  const meanSigned = count ? sumSigned / count : 0;

  const instability = corr.covariance_instability?.score ?? 0;
  const instabilityRegime = corr.covariance_instability?.regime ?? "--";
  const shiftSensitivity = corr.regime_correlation_shift?.sensitivity ?? "--";
  const shiftMagnitude = corr.regime_correlation_shift?.shift_magnitude ?? 0;

  // Crisis coupling: broad basket correlations spiking high together.
  const crisisCoupling = meanAbs >= 0.7 && (strongest?.value ?? 0) >= 0.8;

  let regime: CorrelationRegime;
  if (crisisCoupling) regime = "CRISIS_COUPLING";
  else if (meanAbs >= 0.55) regime = "ELEVATED";
  else if (meanAbs <= 0.2) regime = "DECOUPLED";
  else regime = "NORMAL";

  const warnings: string[] = [];
  if (crisisCoupling) warnings.push("CRISIS CORRELATION COUPLING — DIVERSIFICATION BREAKING DOWN");
  else if (regime === "ELEVATED") warnings.push("ELEVATED CROSS-ASSET CORRELATION — REDUCED DIVERSIFICATION");
  if (instability >= 0.5) warnings.push("COVARIANCE INSTABILITY — CORRELATION STRUCTURE SHIFTING");

  return {
    available: true,
    regime,
    meanAbsCorrelation: meanAbs,
    meanCorrelation: meanSigned,
    instability,
    instabilityRegime,
    crisisCoupling,
    strongestPair: strongest,
    shiftSensitivity,
    shiftMagnitude,
    warnings,
  };
}
