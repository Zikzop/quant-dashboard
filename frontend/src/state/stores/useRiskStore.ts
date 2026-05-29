import { create } from "zustand";
import type {
  PortfolioRisk,
  DrawdownState,
  PropFirmLimits,
  KillSwitchState,
  RiskMetrics,
  CorrelationRisk,
} from "@/types/market";

// Simulated initial state — will be replaced by real-time WebSocket data
const defaultPortfolioRisk: PortfolioRisk = {
  total_exposure: 147200,
  long_exposure: 98400,
  short_exposure: 48800,
  net_exposure: 49600,
  leverage: 2.4,
  beta_exposure: 1.18,
  gross_exposure: 147200,
};

const defaultDrawdown: DrawdownState = {
  daily_drawdown: -0.82,
  weekly_drawdown: -1.47,
  max_drawdown: -4.21,
  daily_high_water: 102340,
  weekly_high_water: 103100,
  underwater_duration: 3,
};

const defaultPropFirm: PropFirmLimits = {
  daily_loss_limit: 5000,
  max_loss_limit: 12000,
  current_daily_loss: 820,
  current_total_loss: 2140,
  remaining_daily_loss: 4180,
  remaining_max_loss: 9860,
  daily_proximity_pct: 16.4,
  max_proximity_pct: 17.8,
  stress_estimate: 2800,
  status: "SAFE",
};

const defaultKillSwitch: KillSwitchState = {
  volatility_kill: { active: true, triggered: false, threshold: 45, current: 28.3 },
  drawdown_kill: { active: true, triggered: false, threshold: 5, current: 0.82 },
  execution_kill: { active: true, triggered: false, anomaly_count: 0 },
  global_kill: false,
};

const defaultRiskMetrics: RiskMetrics = {
  var_95: -2340,
  var_99: -3890,
  cvar_95: -2980,
  cvar_99: -5120,
  sharpe_ratio: 1.42,
  sortino_ratio: 2.03,
  calmar_ratio: 0.89,
};

const defaultCorrelationRisk: CorrelationRisk = {
  max_correlation: 0.74,
  correlated_pairs: [
    { pair: "BTC/ETH", correlation: 0.74 },
    { pair: "ETH/SOL", correlation: 0.68 },
    { pair: "BTC/SOL", correlation: 0.61 },
  ],
  concentration_score: 0.42,
  hidden_factor_exposure: 0.31,
};

interface RiskStore {
  portfolioRisk: PortfolioRisk;
  drawdown: DrawdownState;
  propFirm: PropFirmLimits;
  killSwitch: KillSwitchState;
  riskMetrics: RiskMetrics;
  correlationRisk: CorrelationRisk;

  setPortfolioRisk: (r: PortfolioRisk) => void;
  setDrawdown: (d: DrawdownState) => void;
  setPropFirm: (p: PropFirmLimits) => void;
  setKillSwitch: (k: KillSwitchState) => void;
  setRiskMetrics: (m: RiskMetrics) => void;
  setCorrelationRisk: (c: CorrelationRisk) => void;
  toggleGlobalKill: () => void;
}

export const useRiskStore = create<RiskStore>((set) => ({
  portfolioRisk: defaultPortfolioRisk,
  drawdown: defaultDrawdown,
  propFirm: defaultPropFirm,
  killSwitch: defaultKillSwitch,
  riskMetrics: defaultRiskMetrics,
  correlationRisk: defaultCorrelationRisk,

  setPortfolioRisk: (r) => set({ portfolioRisk: r }),
  setDrawdown: (d) => set({ drawdown: d }),
  setPropFirm: (p) => set({ propFirm: p }),
  setKillSwitch: (k) => set({ killSwitch: k }),
  setRiskMetrics: (m) => set({ riskMetrics: m }),
  setCorrelationRisk: (c) => set({ correlationRisk: c }),
  toggleGlobalKill: () =>
    set((s) => ({
      killSwitch: { ...s.killSwitch, global_kill: !s.killSwitch.global_kill },
    })),
}));
