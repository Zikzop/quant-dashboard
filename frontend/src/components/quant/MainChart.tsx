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
// TYPE CONTRACTS
// ─────────────────────────────────────────────────────────────────────────────

interface ChartBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  ema20: number;
  ema50: number;
  regime?: string;       // e.g. "BULLISH_TRENDING"
  adx?: number;
  volatility?: number;   // GARCH conditional vol
  hmm_state?: number;    // 0=mean-revert 1=trending 2=crisis
}

interface MarketPayload {
  chart_data: ChartBar[];
  regime_label?: string;
  regime_strength?: string;
  adx?: number;
  plus_di?: number;
  minus_di?: number;
  hmm_probabilities?: number[];   // [P(mean-revert), P(trending), P(crisis)]
  garch_vol?: number;
  transition_risk?: string;
  vol_regime?: string;
  persistence?: string;
  liquidity?: string;
  confidence?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// COLOR SEMANTICS  — single source of truth
// All regime/state colors must reference this map.
// ─────────────────────────────────────────────────────────────────────────────

const C = {
  // surface
  bg: "#080809",
  surface: "#0d0d0f",
  border: "#1c1c20",
  borderMid: "#26262c",

  // text tiers
  t1: "#e8e8ea",          // primary — values
  t2: "#8a8a94",          // secondary — labels
  t3: "#46464f",          // tertiary — inactive

  // regime / signal semantic colors
  bullish: "#22c55e",
  bearish: "#ef4444",
  volatile: "#f59e0b",
  crisis: "#ef4444",
  neutral: "#6b7280",
  cyan: "#06b6d4",
  blue: "#3b82f6",
  purple: "#a78bfa",

  // chart series
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
  if (regime.includes("BULLISH")) return C.bullish;
  if (regime.includes("BEARISH")) return C.bearish;
  if (regime.includes("CHOPPY")) return C.volatile;
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
  return s ? (map[s] ?? s) : "—";
}

function formatPct(v?: number): string {
  return v != null ? `${(v * 100).toFixed(1)}%` : "—";
}

function formatNum(v?: number, dp = 2): string {
  return v != null ? v.toFixed(dp) : "—";
}

// ─────────────────────────────────────────────────────────────────────────────
// SUB-COMPONENTS  — atomic, single responsibility
// ─────────────────────────────────────────────────────────────────────────────

/** Horizontal rule with optional label — used as section separator */
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

/** Single metric row in a dense stat block */
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

/** Probability bar — shows a posterior distribution visually */
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

/** Chart legend pill */
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

/** Regime dot indicator with pulse for active states */
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
// REGIME INTELLIGENCE OVERLAY
// Answers: What is the current market state? What regime am I operating in?
// This is the primary cognitive anchor — positioned top-left over chart.
// ─────────────────────────────────────────────────────────────────────────────

function RegimeIntelligenceOverlay({ market }: { market: MarketPayload }) {
  const rColor = regimeColor(market.regime_label);
  const hmm = market.hmm_probabilities ?? [0.33, 0.33, 0.34];
  const isActive =
    market.regime_strength === "TRENDING" ||
    market.regime_strength === "STRONG" ||
    market.regime_strength === "EXTREME";

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
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.25em" }}>
          REGIME ENGINE
        </span>
        <RegimeDot color={rColor} pulse={isActive} />
      </div>

      {/* Primary regime label */}
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
        {strengthLabel(market.regime_strength)}
      </div>
      <div style={{ fontSize: 10, color: C.t2, marginBottom: 10 }}>
        {market.regime_label?.replace("_", " ") ?? "UNKNOWN REGIME"}
      </div>

      <Divider label="DIRECTIONAL" />

      {/* ADX + DI block */}
      <div className="mt-1 space-y-[1px]">
        <StatRow
          label="ADX"
          value={formatNum(market.adx)}
          accent={rColor}
        />
        <StatRow
          label="+DI"
          value={formatNum(market.plus_di)}
          accent={C.bullish}
        />
        <StatRow
          label="−DI"
          value={formatNum(market.minus_di)}
          accent={C.bearish}
        />
        <StatRow
          label="DI SPREAD"
          value={formatNum(
            market.plus_di != null && market.minus_di != null
              ? market.plus_di - market.minus_di
              : undefined
          )}
          accent={
            (market.plus_di ?? 0) > (market.minus_di ?? 0)
              ? C.bullish
              : C.bearish
          }
        />
      </div>

      <Divider label="HMM STATE POSTERIOR" />

      {/* HMM probabilities */}
      <div className="mt-1 space-y-[5px]">
        <ProbabilityBar label="MEAN-REVERT" value={hmm[0]} color={C.cyan} />
        <ProbabilityBar label="TRENDING" value={hmm[1]} color={C.bullish} />
        <ProbabilityBar label="CRISIS" value={hmm[2]} color={C.crisis} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VOLATILITY STATE OVERLAY
// Answers: What is the current volatility regime? Is risk expanding?
// Positioned top-right — secondary cognitive layer.
// ─────────────────────────────────────────────────────────────────────────────

function VolatilityStateOverlay({ market }: { market: MarketPayload }) {
  const volColor =
    market.vol_regime === "EXPANDING" ? C.volatile :
      market.vol_regime === "CONTRACTING" ? C.cyan :
        C.neutral;

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
        {market.vol_regime ?? "—"}
      </div>
      <div style={{ fontSize: 10, color: C.t2, marginBottom: 10 }}>
        GARCH CONDITIONAL VOL
      </div>

      <Divider />

      <div className="space-y-[1px]">
        <StatRow
          label="σ (GARCH)"
          value={formatPct(market.garch_vol)}
          accent={volColor}
        />
        <StatRow
          label="TRANS. RISK"
          value={market.transition_risk ?? "—"}
          accent={
            market.transition_risk === "ELEVATED" ? C.bearish : C.t1
          }
        />
        <StatRow
          label="PERSISTENCE"
          value={market.persistence ?? "—"}
          accent={
            market.persistence === "WEAKENING" ? C.volatile : C.t1
          }
        />
        <StatRow
          label="LIQUIDITY"
          value={market.liquidity ?? "—"}
          accent={
            market.liquidity === "TIGHTENING" ? C.volatile : C.t1
          }
        />
        <StatRow
          label="CONFIDENCE"
          value={
            market.confidence != null
              ? `${market.confidence.toFixed(0)}%`
              : "—"
          }
          accent={
            (market.confidence ?? 0) > 75 ? C.bullish :
              (market.confidence ?? 0) > 50 ? C.volatile :
                C.bearish
          }
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART LEGEND BAR
// Positioned bottom-left — always visible context for series colors
// ─────────────────────────────────────────────────────────────────────────────

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
// MAIN CHART COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function MainChart({ market }: { market: MarketPayload }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !market?.chart_data?.length) return;

    // ── Chart init ────────────────────────────────────────────────────────
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

    // ── Series: Candles ───────────────────────────────────────────────────
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: C.candleUp,
      downColor: C.candleDown,
      borderVisible: false,
      wickUpColor: C.candleUp,
      wickDownColor: C.candleDown,
    });

    // ── Series: Regime background overlays ───────────────────────────────
    // Each overlay covers only the bars belonging to that regime.
    // Slicing is done dynamically using regime field per bar.

    const trendBars = market.chart_data.filter(b => b.hmm_state === 1);
    const volBars = market.chart_data.filter(b => b.hmm_state === 0);
    const crisisBars = market.chart_data.filter(b => b.hmm_state === 2);

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

    // ── Series: EMA 20 ────────────────────────────────────────────────────
    const ema20Series = chart.addSeries(LineSeries, {
      color: C.ema20,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // ── Series: EMA 50 ────────────────────────────────────────────────────
    const ema50Series = chart.addSeries(LineSeries, {
      color: C.ema50,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });

    // ── Series: Volatility histogram (GARCH-driven) ───────────────────────
    const volHistogram = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    });

    // ── Series: Regime transition pulse ───────────────────────────────────
    // Fires a vertical spike at structural breaks detected by regime engine.
    const transitionSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    // ── Data: map raw bars ────────────────────────────────────────────────

    const candles = market.chart_data.map(b => ({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));

    const ema20Data = market.chart_data.map(b => ({
      time: b.time,
      value: b.ema20,
    }));

    const ema50Data = market.chart_data.map(b => ({
      time: b.time,
      value: b.ema50,
    }));

    // Overlay data: use close price as the value (fills behind candles)
    const toOverlay = (bars: ChartBar[]) =>
      bars.map(b => ({ time: b.time, value: b.close }));

    // Vol histogram: abs(close - open) scaled; color by direction
    const volHistData = market.chart_data.map((b, idx) => {
      const garchVol = b.volatility ?? Math.abs(b.close - b.open) * 0.1;
      return {
        time: b.time,
        value: garchVol,
        color: b.close > b.open ? C.volHistBull : C.volHistBear,
      };
    });

    // Transition pulses: detect regime changes between consecutive bars
    const transitionData = market.chart_data.map((b, idx) => {
      const prev = market.chart_data[idx - 1];
      const isTransition = prev && b.regime !== prev.regime;
      return {
        time: b.time,
        value: isTransition ? (volHistData[idx]?.value ?? 0) * 3 : 0,
        color: "rgba(239,68,68,0.9)",
      };
    });

    // ── Set data ──────────────────────────────────────────────────────────
    candleSeries.setData(candles);
    ema20Series.setData(ema20Data);
    ema50Series.setData(ema50Data);
    trendOverlay.setData(toOverlay(trendBars));
    volOverlay.setData(toOverlay(volBars));
    crisisOverlay.setData(toOverlay(crisisBars));
    volHistogram.setData(volHistData);
    transitionSeries.setData(transitionData);

    // ── Markers: structural events ────────────────────────────────────────
    // Only emit markers at confirmed structural events — not aesthetic noise.
    const markers: any[] = [];

    market.chart_data.forEach((b, idx) => {
      const prev = market.chart_data[idx - 1];
      if (!prev) return;

      const entered = b.regime !== prev.regime;
      const isBull = b.regime?.includes("BULLISH") && entered;
      const isBear = b.regime?.includes("BEARISH") && entered;
      const isChoppy = b.regime?.includes("CHOPPY") && entered;

      if (isBull) {
        markers.push({
          time: b.time,
          position: "belowBar",
          color: C.bullish,
          shape: "arrowUp",
          text: "BULL REGIME",
          size: 1,
        });
      } else if (isBear) {
        markers.push({
          time: b.time,
          position: "aboveBar",
          color: C.bearish,
          shape: "arrowDown",
          text: "BEAR REGIME",
          size: 1,
        });
      } else if (isChoppy) {
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

    // ── Responsive resize ─────────────────────────────────────────────────
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
      {/* ── Terminal header bar ─────────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        {/* Left: instrument + session tag */}
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
              BTC / USD
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

        {/* Right: series legend */}
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

      {/* ── Chart canvas area ───────────────────────────────────────────── */}
      <div className="relative">
        <div ref={containerRef} className="w-full" />

        {/* Intelligence overlays — positioned over chart */}
        <RegimeIntelligenceOverlay market={market} />
        <VolatilityStateOverlay market={market} />
        <ChartLegendBar />
      </div>
    </div>
  );
}
