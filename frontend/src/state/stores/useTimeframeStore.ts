import { create } from "zustand";
import type {
  Timeframe,
  TimeframeRegime,
  MTFAlignment,
  HistoricalContext,
  HistoricalRegimeStats,
  MarketPayload,
  ChartBar,
} from "@/types/market";
import { TIMEFRAMES, TF_HIERARCHY } from "@/types/market";

// ─────────────────────────────────────────────────────────────────────────────
// SIMULATED PER-TIMEFRAME REGIME DATA
// In production, each timeframe would come from backend regime engines.
// Here we derive synthetic MTF regimes from the primary market data to
// demonstrate the architecture — the structure is ready for real endpoints.
// ─────────────────────────────────────────────────────────────────────────────

function deriveTimeframeRegimes(market: MarketPayload): TimeframeRegime[] {
  const state = market.market_state;
  const hmm = market.hmm_regime ?? "UNKNOWN";
  const adx = state?.adx ?? 20;
  const confidence = state?.confidence ?? 0.5;
  const trendProb = market.trend_probability ?? 0.5;
  const meanRevProb = market.mean_revert_probability ?? 0.3;
  const crisisProb = market.crisis_probability ?? 0.1;
  const direction = state?.direction ?? "NEUTRAL";
  const strength = state?.trend_strength ?? "WEAK";
  const volRegime = state?.volatility_regime ?? market.vol_regime ?? "NORMAL";

  const htfRegime = hmm;
  const htfDirection = direction;

  const tfData: Record<Timeframe, Partial<TimeframeRegime>> = {
    "1D": {
      regime: htfRegime,
      trend_strength: strength,
      direction: htfDirection,
      volatility_regime: volRegime,
      adx: adx,
      confidence: confidence,
      trend_probability: trendProb,
      mean_revert_probability: meanRevProb,
      crisis_probability: crisisProb,
    },
    "4H": {
      regime: htfRegime,
      trend_strength: strength,
      direction: htfDirection,
      volatility_regime: volRegime,
      adx: adx * 0.92,
      confidence: confidence * 0.95,
      trend_probability: trendProb * 0.93,
      mean_revert_probability: meanRevProb * 1.05,
      crisis_probability: crisisProb * 0.9,
    },
    "1H": {
      regime: adx > 25 ? htfRegime : "MEAN_REVERT",
      trend_strength: adx > 30 ? strength : "WEAK",
      direction: htfDirection,
      volatility_regime: volRegime,
      adx: adx * 0.8,
      confidence: confidence * 0.88,
      trend_probability: trendProb * 0.82,
      mean_revert_probability: meanRevProb * 1.15,
      crisis_probability: crisisProb * 0.85,
    },
    "15m": {
      regime: adx > 30 ? htfRegime : "MEAN_REVERT",
      trend_strength: "WEAK",
      direction: adx > 25 ? htfDirection : "NEUTRAL",
      volatility_regime: "NORMAL",
      adx: adx * 0.65,
      confidence: confidence * 0.75,
      trend_probability: trendProb * 0.7,
      mean_revert_probability: meanRevProb * 1.3,
      crisis_probability: crisisProb * 0.7,
    },
    "5m": {
      regime: "MEAN_REVERT",
      trend_strength: "CHOPPY",
      direction: Math.random() > 0.5 ? "BULLISH" : "BEARISH",
      volatility_regime: "NORMAL",
      adx: adx * 0.5,
      confidence: confidence * 0.6,
      trend_probability: 0.3,
      mean_revert_probability: 0.55,
      crisis_probability: crisisProb * 0.5,
    },
    "1m": {
      regime: "MEAN_REVERT",
      trend_strength: "CHOPPY",
      direction: Math.random() > 0.5 ? "BULLISH" : "BEARISH",
      volatility_regime: "NORMAL",
      adx: adx * 0.35,
      confidence: confidence * 0.45,
      trend_probability: 0.2,
      mean_revert_probability: 0.65,
      crisis_probability: crisisProb * 0.3,
    },
  };

  return TIMEFRAMES.map((tf) => ({
    timeframe: tf,
    regime: tfData[tf].regime ?? "UNKNOWN",
    trend_strength: tfData[tf].trend_strength ?? "WEAK",
    direction: tfData[tf].direction ?? "NEUTRAL",
    volatility_regime: tfData[tf].volatility_regime ?? "NORMAL",
    adx: tfData[tf].adx ?? 15,
    confidence: Math.min(1, Math.max(0, tfData[tf].confidence ?? 0.5)),
    trend_probability: Math.min(1, Math.max(0, tfData[tf].trend_probability ?? 0.3)),
    mean_revert_probability: Math.min(1, Math.max(0, tfData[tf].mean_revert_probability ?? 0.4)),
    crisis_probability: Math.min(1, Math.max(0, tfData[tf].crisis_probability ?? 0.1)),
  }));
}

// ─────────────────────────────────────────────────────────────────────────────
// ALIGNMENT ENGINE — detect agreement/conflict across timeframes
// ─────────────────────────────────────────────────────────────────────────────

function computeAlignment(regimes: TimeframeRegime[]): MTFAlignment {
  if (regimes.length === 0) {
    return { state: "CONFLICT", aligned_count: 0, total: 0, htf_bias: "--", ltf_bias: "--", macro_micro_divergence: false, htf_conflict_penalty: 0, details: [] };
  }

  const htf = regimes.filter((r) => TF_HIERARCHY[r.timeframe] >= 4);
  const ltf = regimes.filter((r) => TF_HIERARCHY[r.timeframe] <= 1);
  const all = regimes;

  const htfDir = htf.length > 0 ? htf[0].direction : "NEUTRAL";
  const ltfDir = ltf.length > 0 ? ltf[ltf.length - 1].direction : "NEUTRAL";

  const htfBullish = htfDir.toUpperCase().includes("BULL");
  const htfBearish = htfDir.toUpperCase().includes("BEAR");
  const ltfBullish = ltfDir.toUpperCase().includes("BULL");
  const ltfBearish = ltfDir.toUpperCase().includes("BEAR");

  const macroMicroDiv = (htfBullish && ltfBearish) || (htfBearish && ltfBullish);

  const dominantDir = htfDir;
  let alignedCount = 0;
  for (const r of all) {
    const rDir = r.direction.toUpperCase();
    const domDir = dominantDir.toUpperCase();
    if (
      (domDir.includes("BULL") && rDir.includes("BULL")) ||
      (domDir.includes("BEAR") && rDir.includes("BEAR")) ||
      (domDir.includes("NEUTRAL") && rDir.includes("NEUTRAL"))
    ) {
      alignedCount++;
    }
  }

  const details: string[] = [];
  let penalty = 0;

  if (macroMicroDiv) {
    details.push(`HTF ${htfDir} vs LTF ${ltfDir} — MACRO/MICRO DIVERGENCE`);
    penalty += 0.3;
  }

  const htfRegime = htf[0]?.regime ?? "";
  const ltfRegime = ltf[ltf.length - 1]?.regime ?? "";
  if (htfRegime.includes("TREND") && ltfRegime.includes("MEAN")) {
    details.push("TRENDING DAILY + MEAN-REVERTING INTRADAY");
    penalty += 0.15;
  }
  if (htfRegime.includes("CRISIS")) {
    details.push("HTF CRISIS REGIME — ALL LTF SIGNALS DEGRADED");
    penalty += 0.4;
  }

  const htfVol = htf[0]?.volatility_regime ?? "";
  if (htfVol.includes("COMPRESS") && (ltf.some((r) => r.volatility_regime.includes("EXPAND")))) {
    details.push("VOL COMPRESSION HTF + EXPANSION LTF — BREAKOUT SETUP");
  }

  if (details.length === 0) details.push("TIMEFRAMES IN AGREEMENT");

  const alignPct = all.length > 0 ? alignedCount / all.length : 0;
  const state: MTFAlignment["state"] =
    alignPct >= 0.7 ? "ALIGNED" : alignPct >= 0.4 ? "PARTIAL" : "CONFLICT";

  return {
    state,
    aligned_count: alignedCount,
    total: all.length,
    htf_bias: htfDir,
    ltf_bias: ltfDir,
    macro_micro_divergence: macroMicroDiv,
    htf_conflict_penalty: Math.min(1, penalty),
    details,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// HISTORICAL CONTEXT ENGINE
// ─────────────────────────────────────────────────────────────────────────────

function computeHistoricalContext(chartData: ChartBar[]): HistoricalContext {
  if (!chartData.length) {
    return {
      current_regime: "UNKNOWN", similar_regime_count: 0,
      historical_win_rate: 0, historical_avg_return: 0,
      historical_avg_vol_after: 0, historical_max_drawdown: 0,
      regime_stats: [], regime_history: [],
    };
  }

  const currentRegime = chartData[chartData.length - 1]?.hmm_regime ?? "UNKNOWN";

  const regimeBuckets: Record<string, { returns: number[]; durations: number[]; vols: number[] }> = {};
  let currentRun = { regime: chartData[0]?.hmm_regime ?? "UNKNOWN", start: 0, bars: 0 };
  const history: Array<{ time: string; regime: string; duration: number }> = [];

  for (let i = 0; i < chartData.length; i++) {
    const bar = chartData[i];
    const regime = bar.hmm_regime ?? "UNKNOWN";

    if (regime !== currentRun.regime) {
      history.push({ time: chartData[currentRun.start]?.time ?? "", regime: currentRun.regime, duration: currentRun.bars });

      if (!regimeBuckets[currentRun.regime]) {
        regimeBuckets[currentRun.regime] = { returns: [], durations: [], vols: [] };
      }
      const endBar = chartData[Math.min(i, chartData.length - 1)];
      const startBar = chartData[currentRun.start];
      if (startBar && endBar && startBar.close > 0) {
        regimeBuckets[currentRun.regime].returns.push(
          ((endBar.close - startBar.close) / startBar.close) * 100
        );
      }
      regimeBuckets[currentRun.regime].durations.push(currentRun.bars);
      if (bar.garch_vol != null) {
        regimeBuckets[currentRun.regime].vols.push(bar.garch_vol);
      }

      currentRun = { regime, start: i, bars: 1 };
    } else {
      currentRun.bars++;
    }
  }
  history.push({ time: chartData[currentRun.start]?.time ?? "", regime: currentRun.regime, duration: currentRun.bars });

  const regimeStats: HistoricalRegimeStats[] = Object.entries(regimeBuckets).map(([regime, data]) => {
    const avgReturn = data.returns.length > 0 ? data.returns.reduce((a, b) => a + b, 0) / data.returns.length : 0;
    const wins = data.returns.filter((r) => r > 0).length;
    const avgDuration = data.durations.length > 0 ? data.durations.reduce((a, b) => a + b, 0) / data.durations.length : 0;
    const avgVol = data.vols.length > 0 ? data.vols.reduce((a, b) => a + b, 0) / data.vols.length : 0;
    const avgDd = data.returns.length > 0 ? Math.min(...data.returns, 0) : 0;

    const transitionsFrom = history.filter((h) => h.regime === regime);
    const nextRegimes: Record<string, number> = {};
    for (let i = 0; i < history.length - 1; i++) {
      if (history[i].regime === regime) {
        const next = history[i + 1].regime;
        nextRegimes[next] = (nextRegimes[next] ?? 0) + 1;
      }
    }
    const totalTrans = Object.values(nextRegimes).reduce((a, b) => a + b, 0) || 1;

    return {
      regime,
      occurrences: data.returns.length,
      avg_duration_bars: avgDuration,
      avg_return_pct: avgReturn,
      win_rate: data.returns.length > 0 ? (wins / data.returns.length) * 100 : 0,
      avg_volatility_after: avgVol,
      avg_drawdown: avgDd,
      transition_to: Object.entries(nextRegimes).map(([r, c]) => ({ regime: r, probability: c / totalTrans })),
    };
  });

  const currentStats = regimeStats.find((s) => s.regime === currentRegime);

  return {
    current_regime: currentRegime,
    similar_regime_count: currentStats?.occurrences ?? 0,
    historical_win_rate: currentStats?.win_rate ?? 0,
    historical_avg_return: currentStats?.avg_return_pct ?? 0,
    historical_avg_vol_after: currentStats?.avg_volatility_after ?? 0,
    historical_max_drawdown: currentStats?.avg_drawdown ?? 0,
    regime_stats: regimeStats,
    regime_history: history,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// STORE
// ─────────────────────────────────────────────────────────────────────────────

interface TimeframeStore {
  activeTimeframe: Timeframe;
  regimes: TimeframeRegime[];
  alignment: MTFAlignment;
  historicalContext: HistoricalContext;

  setActiveTimeframe: (tf: Timeframe) => void;
  updateFromMarket: (market: MarketPayload) => void;
}

export const useTimeframeStore = create<TimeframeStore>((set) => ({
  activeTimeframe: "1D",
  regimes: [],
  alignment: {
    state: "CONFLICT", aligned_count: 0, total: 0,
    htf_bias: "--", ltf_bias: "--",
    macro_micro_divergence: false, htf_conflict_penalty: 0, details: [],
  },
  historicalContext: {
    current_regime: "UNKNOWN", similar_regime_count: 0,
    historical_win_rate: 0, historical_avg_return: 0,
    historical_avg_vol_after: 0, historical_max_drawdown: 0,
    regime_stats: [], regime_history: [],
  },

  setActiveTimeframe: (tf) => set({ activeTimeframe: tf }),

  updateFromMarket: (market) => {
    const regimes = deriveTimeframeRegimes(market);
    const alignment = computeAlignment(regimes);
    const historicalContext = computeHistoricalContext(market.chart_data);
    set({ regimes, alignment, historicalContext });
  },
}));
