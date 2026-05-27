"use client";

import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CandlestickSeries,
  LineSeries,
  AreaSeries,
  HistogramSeries,
} from "lightweight-charts";

import { useEffect, useRef } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// TYPE CONTRACTS — aligned with FastAPI /market payload
// ─────────────────────────────────────────────────────────────────────────────

interface MarketState {
  market_regime?: string;
  volatility_regime?: string;
  trend_persistence?: string;
  transition_risk?: string;
  confidence?: number;
  adx?: number;
  volatility?: number;
  risk_state?: string;
  trend_strength?: string;
  direction?: string;
  plus_di?: number;
  minus_di?: number;
}

interface ChartBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  ema20: number;
  ema50: number;
  adx?: number;
  direction?: string;
  trend_strength?: string;
  hmm_regime?: string;
  trend_probability?: number;
  crisis_probability?: number;
  garch_vol?: number;
  vol_regime?: string;
}

interface MarketPayload {
  symbol?: string;
  chart_data: ChartBar[];
  market_state?: MarketState;
  garch_vol?: number;
  vol_regime?: string;
  hmm_regime?: string;
  mean_revert_probability?: number;
  trend_probability?: number;
  crisis_probability?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// COLOR SEMANTICS  — single source of truth
// ─────────────────────────────────────────────────────────────────────────────

const C = {
  bg: "#080809",
  surface: "#0d0d0f",
  border: "#1c1c20",
  borderMid: "#26262c",
  t1: "#e8e8ea",
  t2: "#8a8a94",
  t3: "#46464f",
  bullish: "#22c55e",
  bearish: "#ef4444",
  volatile: "#f59e0b",
  crisis: "#ef4444",
  neutral: "#6b7280",
  cyan: "#06b6d4",
  blue: "#3b82f6",
  purple: "#a78bfa",
  candleUp: "#22c55e",
  candleDown: "#ef4444",
  ema20: "#06b6d4",
  ema50: "#3b82f6",
  volHistBull: "rgba(34,197,94,0.40)",
  volHistBear: "rgba(239,68,68,0.40)",
  trendOverlay: "rgba(34,197,94,0.07)",
  volatileOverlay: "rgba(245,158,11,0.07)",
  crisisOverlay: "rgba(239,68,68,0.07)",
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function regimeColor(regime?: string): string {
  if (!regime) return C.neutral;
  const r = regime.toUpperCase();
  if (r.includes("BULLISH") || r.includes("TREND")) return C.bullish;
  if (r.includes("BEARISH")) return C.bearish;
  if (r.includes("CRISIS")) return C.crisis;
  if (r.includes("MEAN") || r.includes("CHOPPY")) return C.cyan;
  if (r.includes("VOLAT")) return C.volatile;
  return C.neutral;
}

function directionColor(direction?: string): string {
  if (!direction) return C.neutral;
  const d = direction.toUpperCase();
  if (d.includes("BULL")) return C.bullish;
  if (d.includes("BEAR")) return C.bearish;
  return C.neutral;
}

function strengthLabel(s?: string): string {
  const map: Record<string, string> = {
    CHOPPY: "RANGING",
    WEAK: "WEAK TREND",
    TRENDING: "TRENDING",
    STRONG: "STRONG",
    EXTREME: "EXTREME",
  };
  return s ? (map[s] ?? s) : "--";
}

function volRegimeColor(regime?: string): string {
  if (!regime) return C.neutral;
  const r = regime.toUpperCase();
  if (r.includes("EXPAND")) return C.volatile;
  if (r.includes("COMPRESS") || r.includes("CONTRACT")) return C.cyan;
  return C.neutral;
}

function probFraction(v?: number): number {
  if (v == null || Number.isNaN(v)) return 0;
  return v > 1 ? v / 100 : v;
}

function displayMetric(
  value?: number | null,
  dp = 2
): string {
  if (value == null || Number.isNaN(value)) return "--";
  return value.toFixed(dp);
}

function displayConfidence(confidence?: number): string {
  if (confidence == null || Number.isNaN(confidence)) return "--";
  const pct = confidence <= 1 ? confidence * 100 : confidence;
  return `${pct.toFixed(0)}%`;
}

function finiteNum(value: number | undefined | null, fallback = 0): number {
  if (value == null || !Number.isFinite(value)) return fallback;
  return value;
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

function Divider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 my-1">
      <div className="flex-1 h-px" style={{ background: C.border }} />
      {label && (
        <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.15em" }}>
          {label}
        </span>
      )}
      <div className="flex-1 h-px" style={{ background: C.border }} />
    </div>
  );
}

function StatRow({
  label,
  value,
  accent,
  sub,
}: {
  label: string;
  value: string;
  accent?: string;
  sub?: string;
}) {
  return (
    <div className="flex items-baseline justify-between py-[3px]">
      <span style={{ fontSize: 10, color: C.t2, letterSpacing: "0.06em" }}>
        {label}
      </span>
      <div className="flex items-baseline gap-1">
        {sub && (
          <span style={{ fontSize: 9, color: C.t3 }}>{sub}</span>
        )}
        <span
          style={{
            fontSize: 11,
            fontFamily: "'IBM Plex Mono', monospace",
            fontWeight: 600,
            color: accent ?? C.t1,
            letterSpacing: "0.02em",
          }}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

function ProbabilityBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div className="flex items-center gap-2">
      <span
        style={{
          fontSize: 9,
          color: C.t2,
          width: 72,
          letterSpacing: "0.05em",
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <div
        className="flex-1 h-[3px] rounded-full"
        style={{ background: C.border }}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </div>
      <span
        style={{
          fontSize: 10,
          fontFamily: "'IBM Plex Mono', monospace",
          color: C.t1,
          width: 32,
          textAlign: "right",
        }}
      >
        {(pct * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function LegendPill({
  color,
  label,
}: {
  color: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-[5px]">
      <div
        className="w-4 h-[2px] rounded-full"
        style={{ background: color }}
      />
      <span style={{ fontSize: 10, color: C.t2, letterSpacing: "0.04em" }}>
        {label}
      </span>
    </div>
  );
}

function RegimeDot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <div className="relative flex items-center justify-center w-3 h-3">
      {pulse && (
        <div
          className="absolute w-3 h-3 rounded-full animate-ping opacity-50"
          style={{ background: color }}
        />
      )}
      <div
        className="w-2 h-2 rounded-full"
        style={{ background: color }}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// REGIME INTELLIGENCE OVERLAY — backend market_state (terminal radar)
// ─────────────────────────────────────────────────────────────────────────────

function RegimeIntelligenceOverlay({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const rColor = regimeColor(state?.market_regime ?? market.hmm_regime);
  const dColor = directionColor(state?.direction);
  const isActive =
    state?.trend_strength === "TRENDING" ||
    state?.trend_strength === "STRONG" ||
    state?.trend_strength === "EXTREME";

  const plusDi = state?.plus_di;
  const minusDi = state?.minus_di;

  return (
    <div
      className="absolute top-4 left-4 z-50 w-[220px]"
      style={{
        background: "rgba(8,8,9,0.96)",
        border: `1px solid ${C.borderMid}`,
        borderRadius: 4,
        padding: "12px 14px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.25em" }}>
          REGIME ENGINE
        </span>
        <RegimeDot color={rColor} pulse={isActive} />
      </div>

      <div
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: rColor,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          marginBottom: 2,
        }}
      >
        {strengthLabel(state?.trend_strength)}
      </div>
      <div style={{ fontSize: 10, color: C.t2, marginBottom: 10 }}>
        {state?.market_regime?.replace(/_/g, " ") ?? "--"}
      </div>

      <Divider label="DIRECTIONAL" />

      <div className="mt-1 space-y-[1px]">
        <StatRow
          label="REGIME"
          value={state?.market_regime ?? "--"}
          accent={rColor}
        />
        <StatRow
          label="TREND STR."
          value={strengthLabel(state?.trend_strength)}
          accent={rColor}
        />
        <StatRow
          label="DIRECTION"
          value={state?.direction ?? "--"}
          accent={dColor}
        />
        <StatRow
          label="ADX"
          value={state?.adx?.toFixed(2) ?? "--"}
          accent={rColor}
        />
        <StatRow
          label="+DI"
          value={state?.plus_di?.toFixed(2) ?? "--"}
          accent={C.bullish}
        />
        <StatRow
          label="−DI"
          value={state?.minus_di?.toFixed(2) ?? "--"}
          accent={C.bearish}
        />
        <StatRow
          label="DI SPREAD"
          value={
            plusDi != null && minusDi != null
              ? displayMetric(plusDi - minusDi)
              : "--"
          }
          accent={
            plusDi != null && minusDi != null && plusDi > minusDi
              ? C.bullish
              : C.bearish
          }
        />
      </div>

      <Divider label="HMM STATE POSTERIOR" />

      <div className="mt-1 space-y-[5px]">
        <ProbabilityBar
          label="MEAN-REVERT"
          value={probFraction(market.mean_revert_probability)}
          color={C.cyan}
        />
        <ProbabilityBar
          label="TRENDING"
          value={probFraction(market.trend_probability)}
          color={C.bullish}
        />
        <ProbabilityBar
          label="CRISIS"
          value={probFraction(market.crisis_probability)}
          color={C.crisis}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VOLATILITY STATE OVERLAY — backend market_state + GARCH surface
// ─────────────────────────────────────────────────────────────────────────────

function VolatilityStateOverlay({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const volRegime =
    state?.volatility_regime ?? market.vol_regime ?? "--";
  const volColor = volRegimeColor(volRegime);

  const garchDisplay =
    state?.volatility != null
      ? `${displayMetric(state.volatility)}%`
      : market.garch_vol != null
        ? displayMetric(market.garch_vol, 4)
        : "--";

  const transitionRisk = state?.transition_risk ?? "--";
  const persistence = state?.trend_persistence ?? "--";
  const confidence = state?.confidence;

  return (
    <div
      className="absolute top-4 right-4 z-50 w-[196px]"
      style={{
        background: "rgba(8,8,9,0.96)",
        border: `1px solid ${C.borderMid}`,
        borderRadius: 4,
        padding: "12px 14px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.25em" }}>
          VOL SURFACE
        </span>
        <RegimeDot color={volColor} />
      </div>

      <div
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: volColor,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
          marginBottom: 2,
        }}
      >
        {volRegime}
      </div>
      <div style={{ fontSize: 10, color: C.t2, marginBottom: 10 }}>
        GARCH CONDITIONAL VOL
      </div>

      <Divider />

      <div className="space-y-[1px]">
        <StatRow
          label="σ (GARCH)"
          value={garchDisplay}
          accent={volColor}
        />
        <StatRow
          label="TRANS. RISK"
          value={transitionRisk}
          accent={
            transitionRisk === "ELEVATED" ? C.bearish : C.t1
          }
        />
        <StatRow
          label="PERSISTENCE"
          value={persistence}
          accent={
            persistence === "WEAK" ? C.volatile :
              persistence === "STRONG" ? C.bullish :
                C.t1
          }
        />
        <StatRow
          label="RISK STATE"
          value={state?.risk_state ?? "--"}
          accent={C.t1}
        />
        <StatRow
          label="CONFIDENCE"
          value={displayConfidence(confidence)}
          accent={
            (confidence ?? 0) > 0.75 ? C.bullish :
              (confidence ?? 0) > 0.5 ? C.volatile :
                C.bearish
          }
        />
      </div>
    </div>
  );
}

function ChartLegendBar() {
  return (
    <div
      className="absolute bottom-4 left-4 z-40 flex items-center gap-4"
      style={{
        background: "rgba(8,8,9,0.88)",
        border: `1px solid ${C.border}`,
        borderRadius: 3,
        padding: "5px 10px",
      }}
    >
      <LegendPill color={C.candleUp} label="PRICE" />
      <LegendPill color={C.ema20} label="EMA 20" />
      <LegendPill color={C.ema50} label="EMA 50" />
      <LegendPill color={C.volatile} label="VOL HIST" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN CHART — REAL OHLCV → engines → market_state → terminal overlay
// ─────────────────────────────────────────────────────────────────────────────

export default function MainChart({ market }: { market: MarketPayload }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !market?.chart_data?.length) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: C.bg },
        textColor: C.t2,
        fontFamily: "'IBM Plex Mono', monospace",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: C.border },
        horzLines: { color: C.border },
      },
      crosshair: {
        vertLine: { color: C.borderMid, labelBackgroundColor: "#1c1c20" },
        horzLine: { color: C.borderMid, labelBackgroundColor: "#1c1c20" },
      },
      width: containerRef.current.clientWidth,
      height: 680,
      rightPriceScale: {
        borderColor: C.border,
        textColor: C.t2,
        minimumWidth: 64,
      },
      timeScale: {
        borderColor: C.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: C.candleUp,
      downColor: C.candleDown,
      borderVisible: false,
      wickUpColor: C.candleUp,
      wickDownColor: C.candleDown,
    });

    const trendBars = market.chart_data.filter(
      (b) => b.hmm_regime === "TRENDING"
    );
    const volBars = market.chart_data.filter(
      (b) => b.hmm_regime === "MEAN_REVERT"
    );
    const crisisBars = market.chart_data.filter(
      (b) => b.hmm_regime === "CRISIS"
    );

    const makeOverlay = (color: string) =>
      chart.addSeries(AreaSeries, {
        lineColor: "rgba(0,0,0,0)",
        topColor: color,
        bottomColor: "rgba(0,0,0,0)",
        lineWidth: 1,
        priceScaleId: "right",
        lastValueVisible: false,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });

    const trendOverlay = makeOverlay(C.trendOverlay);
    const volOverlay = makeOverlay(C.volatileOverlay);
    const crisisOverlay = makeOverlay(C.crisisOverlay);

    const ema20Series = chart.addSeries(LineSeries, {
      color: C.ema20,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const ema50Series = chart.addSeries(LineSeries, {
      color: C.ema50,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    const volHistogram = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    const transitionSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    const candles = market.chart_data.map((b) => ({
      time: b.time,
      open: finiteNum(b.open),
      high: finiteNum(b.high),
      low: finiteNum(b.low),
      close: finiteNum(b.close),
    }));

    const ema20Data = market.chart_data.map((b) => ({
      time: b.time,
      value: finiteNum(b.ema20),
    }));

    const ema50Data = market.chart_data.map((b) => ({
      time: b.time,
      value: finiteNum(b.ema50),
    }));

    const toOverlay = (bars: ChartBar[]) =>
      bars.map((b) => ({ time: b.time, value: b.close }));

    const volHistData = market.chart_data.map((b) => {
      const garchVol = finiteNum(b.garch_vol);
      return {
        time: b.time,
        value: garchVol,
        color: finiteNum(b.close) > finiteNum(b.open)
          ? C.volHistBull
          : C.volHistBear,
      };
    });

    const transitionData = market.chart_data.map((b, idx) => {
      const prev = market.chart_data[idx - 1];
      const hmmShift =
        prev && b.hmm_regime && prev.hmm_regime !== b.hmm_regime;
      const dirShift =
        prev && b.direction && prev.direction !== b.direction;
      const isTransition = hmmShift || dirShift;
      return {
        time: b.time,
        value: isTransition ? (volHistData[idx]?.value ?? 0) * 3 : 0,
        color: "rgba(239,68,68,0.9)",
      };
    });

    candleSeries.setData(candles);
    ema20Series.setData(ema20Data);
    ema50Series.setData(ema50Data);
    trendOverlay.setData(toOverlay(trendBars));
    volOverlay.setData(toOverlay(volBars));
    crisisOverlay.setData(toOverlay(crisisBars));
    volHistogram.setData(volHistData);
    transitionSeries.setData(transitionData);

    const markers: Array<{
      time: string;
      position: "aboveBar" | "belowBar";
      color: string;
      shape: "arrowUp" | "arrowDown" | "circle";
      text: string;
      size: number;
    }> = [];

    market.chart_data.forEach((b, idx) => {
      const prev = market.chart_data[idx - 1];
      if (!prev) return;

      const dirChanged =
        b.direction && prev.direction && b.direction !== prev.direction;
      const hmmChanged =
        b.hmm_regime && prev.hmm_regime && b.hmm_regime !== prev.hmm_regime;

      if (!dirChanged && !hmmChanged) return;

      const dir = (b.direction ?? "").toUpperCase();

      if (dir.includes("BULL")) {
        markers.push({
          time: b.time,
          position: "belowBar",
          color: C.bullish,
          shape: "arrowUp",
          text: "BULL REGIME",
          size: 1,
        });
      } else if (dir.includes("BEAR")) {
        markers.push({
          time: b.time,
          position: "aboveBar",
          color: C.bearish,
          shape: "arrowDown",
          text: "BEAR REGIME",
          size: 1,
        });
      } else if (b.hmm_regime === "CRISIS" || hmmChanged) {
        markers.push({
          time: b.time,
          position: "aboveBar",
          color: C.volatile,
          shape: "circle",
          text: "REGIME BREAK",
          size: 1,
        });
      }
    });

    if (markers.length) createSeriesMarkers(candleSeries, markers);

    const handleResize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [market]);

  return (
    <div
      className="relative w-full"
      style={{ background: C.bg, fontFamily: "'IBM Plex Sans', sans-serif" }}
    >
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: C.t1,
                letterSpacing: "0.08em",
                fontFamily: "'IBM Plex Mono', monospace",
              }}
            >
              {market.symbol?.replace("-", " / ") ?? "BTC / USD"}
            </span>
            <span
              style={{
                fontSize: 9,
                color: C.t3,
                background: C.surface,
                border: `1px solid ${C.border}`,
                borderRadius: 2,
                padding: "1px 5px",
                letterSpacing: "0.1em",
              }}
            >
              PERPETUAL
            </span>
          </div>
          <div className="h-3 w-px" style={{ background: C.border }} />
          <span style={{ fontSize: 10, color: C.t3, letterSpacing: "0.06em" }}>
            INSTITUTIONAL ANALYTICS
          </span>
        </div>

        <div className="flex items-center gap-5">
          <LegendPill color={C.ema20} label="EMA 20" />
          <LegendPill color={C.ema50} label="EMA 50" />
          <div className="h-3 w-px" style={{ background: C.border }} />
          <span
            style={{
              fontSize: 9,
              color: C.t3,
              letterSpacing: "0.12em",
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          >
            ADX-14 · GARCH · HMM-3S
          </span>
        </div>
      </div>

      <div className="relative">
        <div ref={containerRef} className="w-full" />

        <RegimeIntelligenceOverlay market={market} />
        <VolatilityStateOverlay market={market} />
        <ChartLegendBar />
      </div>
    </div>
  );
}
