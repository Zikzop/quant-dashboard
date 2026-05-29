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
import {
  TIMEFRAMES,
  TF_HIERARCHY,
  DEFAULT_HISTORICAL_RANGE,
  type HistoricalRange,
} from "@/types/market";
import { useMarketStore } from "./useMarketStore";
import { fetchMarketTimeframe } from "@/lib/api";

export type CacheKey = `${Timeframe}|${HistoricalRange}`;

export function makeCacheKey(tf: Timeframe, range: HistoricalRange): CacheKey {
  return `${tf}|${range}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// EXTRACT REAL REGIME DATA from a backend MarketPayload
// ─────────────────────────────────────────────────────────────────────────────

function probNorm(v?: number): number {
  if (v == null || Number.isNaN(v)) return 0;
  return v > 1 ? v / 100 : v;
}

function extractRegimeFromPayload(
  tf: Timeframe,
  market: MarketPayload,
): TimeframeRegime {
  const state = market.market_state;
  return {
    timeframe: tf,
    regime: market.hmm_regime ?? "UNKNOWN",
    trend_strength: state?.trend_strength ?? "WEAK",
    direction: state?.direction ?? "NEUTRAL",
    volatility_regime:
      state?.volatility_regime ?? market.vol_regime ?? "NORMAL",
    adx: state?.adx ?? 0,
    confidence: Math.min(1, Math.max(0, state?.confidence ?? 0.5)),
    trend_probability: probNorm(market.trend_probability),
    mean_revert_probability: probNorm(market.mean_revert_probability),
    crisis_probability: probNorm(market.crisis_probability),
  };
}

function placeholderRegime(tf: Timeframe): TimeframeRegime {
  return {
    timeframe: tf,
    regime: "LOADING",
    trend_strength: "--",
    direction: "NEUTRAL",
    volatility_regime: "NORMAL",
    adx: 0,
    confidence: 0,
    trend_probability: 0,
    mean_revert_probability: 0,
    crisis_probability: 0,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// ALIGNMENT ENGINE — detect agreement/conflict across timeframes
// ─────────────────────────────────────────────────────────────────────────────

function computeAlignment(regimes: TimeframeRegime[]): MTFAlignment {
  const loaded = regimes.filter((r) => r.regime !== "LOADING");
  if (loaded.length === 0) {
    return {
      state: "CONFLICT",
      aligned_count: 0,
      total: 0,
      htf_bias: "--",
      ltf_bias: "--",
      macro_micro_divergence: false,
      htf_conflict_penalty: 0,
      details: [],
    };
  }

  const htf = loaded.filter((r) => TF_HIERARCHY[r.timeframe] >= 4);
  const ltf = loaded.filter((r) => TF_HIERARCHY[r.timeframe] <= 1);
  const all = loaded;

  const htfDir = htf.length > 0 ? htf[0].direction : "NEUTRAL";
  const ltfDir = ltf.length > 0 ? ltf[ltf.length - 1].direction : "NEUTRAL";

  const htfBullish = htfDir.toUpperCase().includes("BULL");
  const htfBearish = htfDir.toUpperCase().includes("BEAR");
  const ltfBullish = ltfDir.toUpperCase().includes("BULL");
  const ltfBearish = ltfDir.toUpperCase().includes("BEAR");

  const macroMicroDiv =
    (htfBullish && ltfBearish) || (htfBearish && ltfBullish);

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
    details.push(
      `HTF ${htfDir} vs LTF ${ltfDir} — MACRO/MICRO DIVERGENCE`,
    );
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
  if (
    htfVol.includes("COMPRESS") &&
    ltf.some((r) => r.volatility_regime.includes("EXPAND"))
  ) {
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
      current_regime: "UNKNOWN",
      similar_regime_count: 0,
      historical_win_rate: 0,
      historical_avg_return: 0,
      historical_avg_vol_after: 0,
      historical_max_drawdown: 0,
      regime_stats: [],
      regime_history: [],
    };
  }

  const currentRegime =
    chartData[chartData.length - 1]?.hmm_regime ?? "UNKNOWN";

  const regimeBuckets: Record<
    string,
    { returns: number[]; durations: number[]; vols: number[] }
  > = {};
  let currentRun = {
    regime: chartData[0]?.hmm_regime ?? "UNKNOWN",
    start: 0,
    bars: 0,
  };
  const history: Array<{
    time: string;
    regime: string;
    duration: number;
  }> = [];

  for (let i = 0; i < chartData.length; i++) {
    const bar = chartData[i];
    const regime = bar.hmm_regime ?? "UNKNOWN";

    if (regime !== currentRun.regime) {
      const timeVal = chartData[currentRun.start]?.time;
      history.push({
        time: typeof timeVal === "number" ? new Date(timeVal * 1000).toISOString() : (timeVal ?? ""),
        regime: currentRun.regime,
        duration: currentRun.bars,
      });

      if (!regimeBuckets[currentRun.regime]) {
        regimeBuckets[currentRun.regime] = {
          returns: [],
          durations: [],
          vols: [],
        };
      }
      const endBar = chartData[Math.min(i, chartData.length - 1)];
      const startBar = chartData[currentRun.start];
      if (startBar && endBar && startBar.close > 0) {
        regimeBuckets[currentRun.regime].returns.push(
          ((endBar.close - startBar.close) / startBar.close) * 100,
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
  const lastTimeVal = chartData[currentRun.start]?.time;
  history.push({
    time: typeof lastTimeVal === "number" ? new Date(lastTimeVal * 1000).toISOString() : (lastTimeVal ?? ""),
    regime: currentRun.regime,
    duration: currentRun.bars,
  });

  const regimeStats: HistoricalRegimeStats[] = Object.entries(
    regimeBuckets,
  ).map(([regime, data]) => {
    const avgReturn =
      data.returns.length > 0
        ? data.returns.reduce((a, b) => a + b, 0) / data.returns.length
        : 0;
    const wins = data.returns.filter((r) => r > 0).length;
    const avgDuration =
      data.durations.length > 0
        ? data.durations.reduce((a, b) => a + b, 0) / data.durations.length
        : 0;
    const avgVol =
      data.vols.length > 0
        ? data.vols.reduce((a, b) => a + b, 0) / data.vols.length
        : 0;
    const avgDd =
      data.returns.length > 0 ? Math.min(...data.returns, 0) : 0;

    const nextRegimes: Record<string, number> = {};
    for (let i = 0; i < history.length - 1; i++) {
      if (history[i].regime === regime) {
        const next = history[i + 1].regime;
        nextRegimes[next] = (nextRegimes[next] ?? 0) + 1;
      }
    }
    const totalTrans =
      Object.values(nextRegimes).reduce((a, b) => a + b, 0) || 1;

    return {
      regime,
      occurrences: data.returns.length,
      avg_duration_bars: avgDuration,
      avg_return_pct: avgReturn,
      win_rate:
        data.returns.length > 0 ? (wins / data.returns.length) * 100 : 0,
      avg_volatility_after: avgVol,
      avg_drawdown: avgDd,
      transition_to: Object.entries(nextRegimes).map(([r, c]) => ({
        regime: r,
        probability: c / totalTrans,
      })),
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
  /** Canonical active asset id (BTC, DXY, …). */
  activeAsset: string;
  /** @deprecated Use activeAsset — kept for gradual migration. */
  activeSymbol: string;
  activeTimeframe: Timeframe;
  activeRange: HistoricalRange;
  timeframeCache: Partial<Record<CacheKey, MarketPayload>>;
  loadingTimeframes: Timeframe[];
  regimes: TimeframeRegime[];
  alignment: MTFAlignment;
  historicalContext: HistoricalContext;

  setActiveTimeframe: (tf: Timeframe) => void;
  setActiveAsset: (assetId: string) => void;
  /** @deprecated Use setActiveAsset */
  setActiveSymbol: (symbol: string) => void;
  setActiveRange: (range: HistoricalRange) => void;
  fetchTimeframe: (tf: Timeframe) => Promise<void>;
  setTimeframeData: (tf: Timeframe, data: MarketPayload) => void;
  initializeAllTimeframes: () => void;
  updateFromMarket: (market: MarketPayload) => void;
}

const EMPTY_ALIGNMENT: MTFAlignment = {
  state: "CONFLICT",
  aligned_count: 0,
  total: 0,
  htf_bias: "--",
  ltf_bias: "--",
  macro_micro_divergence: false,
  htf_conflict_penalty: 0,
  details: [],
};

const EMPTY_CONTEXT: HistoricalContext = {
  current_regime: "UNKNOWN",
  similar_regime_count: 0,
  historical_win_rate: 0,
  historical_avg_return: 0,
  historical_avg_vol_after: 0,
  historical_max_drawdown: 0,
  regime_stats: [],
  regime_history: [],
};

function resetMtfState() {
  return {
    timeframeCache: {} as Partial<Record<CacheKey, MarketPayload>>,
    regimes: TIMEFRAMES.map(placeholderRegime),
    alignment: EMPTY_ALIGNMENT,
    historicalContext: EMPTY_CONTEXT,
  };
}

function applyActiveMarket(data: MarketPayload) {
  useMarketStore.getState().setMarket(data);
}

export const useTimeframeStore = create<TimeframeStore>((set, get) => ({
  activeTimeframe: "1D",
  activeAsset: "BTC",
  activeSymbol: "BTC",
  activeRange: DEFAULT_HISTORICAL_RANGE,
  timeframeCache: {},
  loadingTimeframes: [],
  regimes: TIMEFRAMES.map(placeholderRegime),
  alignment: EMPTY_ALIGNMENT,
  historicalContext: EMPTY_CONTEXT,

  setActiveTimeframe: (tf) => {
    set({ activeTimeframe: tf });
    const key = makeCacheKey(tf, get().activeRange);
    const cached = get().timeframeCache[key];
    if (cached) {
      applyActiveMarket(cached);
      set({ historicalContext: computeHistoricalContext(cached.chart_data) });
    } else {
      useMarketStore.getState().setLoading(true);
      get().fetchTimeframe(tf);
    }
  },

  setActiveAsset: (assetId) => {
    if (assetId === get().activeAsset) return;
    useMarketStore.getState().setLoading(true);
    set({
      activeAsset: assetId,
      activeSymbol: assetId,
      ...resetMtfState(),
    });
    const activeTF = get().activeTimeframe;
    get().fetchTimeframe(activeTF);
    TIMEFRAMES.filter((tf) => tf !== activeTF).forEach((tf) =>
      get().fetchTimeframe(tf),
    );
  },

  setActiveSymbol: (symbol) => {
    get().setActiveAsset(symbol);
  },

  setActiveRange: (range) => {
    if (range === get().activeRange) return;
    useMarketStore.getState().setLoading(true);
    set({
      activeRange: range,
      ...resetMtfState(),
    });
    const activeTF = get().activeTimeframe;
    get().fetchTimeframe(activeTF);
    TIMEFRAMES.filter((tf) => tf !== activeTF).forEach((tf) =>
      get().fetchTimeframe(tf),
    );
  },

  fetchTimeframe: async (tf) => {
    const { loadingTimeframes, activeAsset, activeRange } = get();
    if (loadingTimeframes.includes(tf)) return;

    set({ loadingTimeframes: [...loadingTimeframes, tf] });

    const requestAsset = activeAsset;
    const requestRange = activeRange;
    try {
      const data = await fetchMarketTimeframe(tf, requestAsset, requestRange);

      if (
        get().activeAsset !== requestAsset ||
        get().activeRange !== requestRange
      ) {
        return;
      }

      get().setTimeframeData(tf, data);

      if (get().activeTimeframe === tf) {
        applyActiveMarket(data);
        set({
          historicalContext: computeHistoricalContext(data.chart_data),
        });
      }
    } catch (err) {
      console.error(`[MTF] Failed to fetch ${tf}:`, err);
      if (get().activeTimeframe === tf) {
        useMarketStore.getState().setError(
          err instanceof Error ? err.message : `Failed to load ${tf}`,
        );
      }
    } finally {
      set((s) => ({
        loadingTimeframes: s.loadingTimeframes.filter((t) => t !== tf),
      }));
    }
  },

  setTimeframeData: (tf, data) => {
    const key = makeCacheKey(tf, get().activeRange);
    const cache = { ...get().timeframeCache, [key]: data };

    const regimes = TIMEFRAMES.map((t) => {
      const cached = cache[makeCacheKey(t, get().activeRange)];
      if (cached) return extractRegimeFromPayload(t, cached);
      return placeholderRegime(t);
    });

    const alignment = computeAlignment(regimes);
    const isActiveTF = tf === get().activeTimeframe;

    set({
      timeframeCache: cache,
      regimes,
      alignment,
      ...(isActiveTF
        ? { historicalContext: computeHistoricalContext(data.chart_data) }
        : {}),
    });
  },

  initializeAllTimeframes: () => {
    TIMEFRAMES.forEach((tf) => get().fetchTimeframe(tf));
  },

  updateFromMarket: (market) => {
    get().setTimeframeData("1D", market);
  },
}));
