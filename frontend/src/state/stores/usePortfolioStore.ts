import { create } from "zustand";
import type {
  PortfolioAllocation,
  PerformanceAttribution,
  RiskContribution,
  EquityCurveDiagnostics,
  Position,
} from "@/types/market";

const defaultAllocation: PortfolioAllocation = {
  by_asset: [
    { asset: "BTC-PERP", weight: 0.45, pnl: 1240 },
    { asset: "ETH-PERP", weight: 0.25, pnl: -320 },
    { asset: "SOL-PERP", weight: 0.15, pnl: 480 },
    { asset: "ARB-PERP", weight: 0.10, pnl: 90 },
    { asset: "AVAX-PERP", weight: 0.05, pnl: -60 },
  ],
  by_strategy: [
    { strategy: "Trend Following", weight: 0.40, pnl: 980 },
    { strategy: "Mean Reversion", weight: 0.30, pnl: 340 },
    { strategy: "Momentum", weight: 0.20, pnl: 120 },
    { strategy: "Statistical Arb", weight: 0.10, pnl: -10 },
  ],
  by_vol_contribution: [
    { source: "BTC-PERP", vol_contribution: 0.52 },
    { source: "ETH-PERP", vol_contribution: 0.24 },
    { source: "SOL-PERP", vol_contribution: 0.14 },
    { source: "ARB-PERP", vol_contribution: 0.07 },
    { source: "AVAX-PERP", vol_contribution: 0.03 },
  ],
};

const defaultAttribution: PerformanceAttribution = {
  return_contributors: [
    { source: "BTC Trend", contribution: 1.2 },
    { source: "ETH Momentum", contribution: 0.6 },
    { source: "SOL Mean Rev", contribution: 0.4 },
  ],
  loss_contributors: [
    { source: "ETH Short", contribution: -0.8 },
    { source: "ARB Scalp", contribution: -0.3 },
  ],
};

const defaultRiskContribution: RiskContribution = {
  contributors: [
    { source: "BTC-PERP", risk_pct: 48, marginal_var: 1120 },
    { source: "ETH-PERP", risk_pct: 26, marginal_var: 610 },
    { source: "SOL-PERP", risk_pct: 15, marginal_var: 350 },
    { source: "ARB-PERP", risk_pct: 7, marginal_var: 160 },
    { source: "AVAX-PERP", risk_pct: 4, marginal_var: 100 },
  ],
  dominant_factor: "BTC-PERP",
};

const now = Date.now();
const equityPoints = Array.from({ length: 60 }, (_, i) => ({
  time: new Date(now - (59 - i) * 86400000).toISOString().slice(0, 10),
  value: 100000 + Math.sin(i * 0.15) * 2000 + i * 50 + (Math.random() - 0.4) * 500,
}));

const defaultEquity: EquityCurveDiagnostics = {
  smoothness: 0.72,
  equity_volatility: 2.1,
  underwater_periods: [
    { start: equityPoints[10].time, end: equityPoints[18].time, depth: -2.4 },
    { start: equityPoints[35].time, end: equityPoints[42].time, depth: -1.8 },
  ],
  equity_curve: equityPoints,
};

const defaultPositions: Position[] = [
  { symbol: "BTC-PERP", side: "LONG", size: 0.8, entry_price: 67200, current_price: 67540, unrealized_pnl: 272, realized_pnl: 1240, leverage: 3 },
  { symbol: "ETH-PERP", side: "SHORT", size: 5.0, entry_price: 3860, current_price: 3842, unrealized_pnl: 90, realized_pnl: -320, leverage: 2 },
  { symbol: "SOL-PERP", side: "LONG", size: 80, entry_price: 176.4, current_price: 178.1, unrealized_pnl: 136, realized_pnl: 480, leverage: 2 },
];

interface PortfolioStore {
  allocation: PortfolioAllocation;
  attribution: PerformanceAttribution;
  riskContribution: RiskContribution;
  equity: EquityCurveDiagnostics;
  positions: Position[];
  totalPnl: number;

  setAllocation: (a: PortfolioAllocation) => void;
  setAttribution: (a: PerformanceAttribution) => void;
  setRiskContribution: (r: RiskContribution) => void;
  setEquity: (e: EquityCurveDiagnostics) => void;
  setPositions: (p: Position[]) => void;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  allocation: defaultAllocation,
  attribution: defaultAttribution,
  riskContribution: defaultRiskContribution,
  equity: defaultEquity,
  positions: defaultPositions,
  totalPnl: 1430,

  setAllocation: (a) => set({ allocation: a }),
  setAttribution: (a) => set({ attribution: a }),
  setRiskContribution: (r) => set({ riskContribution: r }),
  setEquity: (e) => set({ equity: e }),
  setPositions: (p) => set({ positions: p }),
}));
