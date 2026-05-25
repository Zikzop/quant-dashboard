import { MarketState } from "@/types/market"

export function interpretMarketState(
  state: MarketState
) {

  const alerts: string[] = []

  // =========================
  // VOLATILITY
  // =========================

  if (
    state.volatility_regime ===
    "EXPANDING"
  ) {

    alerts.push(
      "Volatility expansion detected"
    )
  }

  // =========================
  // TREND
  // =========================

  if (
    state.trend_persistence ===
    "WEAK"
  ) {

    alerts.push(
      "Trend persistence weakening"
    )
  }

  // =========================
  // RISK
  // =========================

  if (
    state.transition_risk ===
    "ELEVATED"
  ) {

    alerts.push(
      "Elevated transition instability"
    )
  }

  return {

    alerts
  }
}