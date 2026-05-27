import { create } from "zustand";
import type { AlphaDiagnostics } from "@/types/market";

const defaultAlpha: AlphaDiagnostics = {
  rolling_sharpe: 1.42,
  rolling_sharpe_trend: "STABLE",
  ic_decay: 0.03,
  winrate_30d: 58.2,
  winrate_7d: 54.1,
  winrate_stability: "STABLE",
  regime_performance: {
    TRENDING: 2.4,
    MEAN_REVERT: 0.8,
    CRISIS: -1.2,
    VOLATILE: -0.3,
  },
  feature_drift: 0.12,
  signal_stability: 0.84,
  alpha_decay_rate: 0.02,
  edge_reliability: 0.76,
  trade_distribution: { long_pct: 62, short_pct: 38, avg_hold_hours: 4.2 },
  recent_pnl: [120, -45, 210, 80, -30, 160, -90, 55, 200, -20, 140, 75, -60, 190, 110],
};

interface AlphaStore {
  alpha: AlphaDiagnostics;
  setAlpha: (a: AlphaDiagnostics) => void;
}

export const useAlphaStore = create<AlphaStore>((set) => ({
  alpha: defaultAlpha,
  setAlpha: (a) => set({ alpha: a }),
}));
