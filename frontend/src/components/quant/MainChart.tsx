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
import { useEffect, useRef, useMemo } from "react";
import { C, regimeColor, statusColor, proximityColor } from "@/lib/colors";
import { fmt, fmtPct, probFraction, finiteNum } from "@/lib/format";
import { useRiskStore } from "@/state/stores/useRiskStore";
import { useAlphaStore } from "@/state/stores/useAlphaStore";
import { useExecutionStore } from "@/state/stores/useExecutionStore";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import MTFAlignmentOverlay from "@/components/mtf/MTFAlignmentOverlay";
import type { MarketPayload, EntryQuality } from "@/types/market";

// ─────────────────────────────────────────────────────────────────────────────
// ENTRY QUALITY ENGINE — compute live trade quality from all available signals
// ─────────────────────────────────────────────────────────────────────────────

function computeEntryQuality(
  market: MarketPayload,
  riskState: { drawdownPct: number; propProximity: number; leverage: number },
  alphaState: { sharpe: number; winrate7d: number; signalStability: number },
  execState: { avgSlippage: number; latency: number },
  htfPenalty = 0
): EntryQuality {
  const state = market.market_state;
  const warnings: string[] = [];
  const suppressionReasons: string[] = [];

  const regimeAlignment = (() => {
    const hmm = market.hmm_regime?.toUpperCase() ?? "";
    if (hmm.includes("TRENDING")) return 0.85;
    if (hmm.includes("MEAN")) return 0.6;
    if (hmm.includes("CRISIS")) return 0.1;
    return 0.4;
  })();

  const volSuitability = (() => {
    const vol = state?.volatility ?? market.volatility ?? 0;
    if (vol > 60) { warnings.push("EXTREME VOLATILITY"); return 0.15; }
    if (vol > 40) { warnings.push("HIGH VOLATILITY"); return 0.35; }
    if (vol < 5) return 0.4;
    return 0.8;
  })();

  const trendStrength = (() => {
    const adx = state?.adx ?? 0;
    if (adx > 40) return 0.9;
    if (adx > 25) return 0.65;
    if (adx > 15) return 0.35;
    return 0.15;
  })();

  const liquidityScore = execState.avgSlippage < 2 ? 0.85 : execState.avgSlippage < 5 ? 0.5 : 0.2;
  if (execState.avgSlippage > 5) warnings.push("POOR LIQUIDITY");

  const correlationEnv = 0.7;

  const executionConditions = (() => {
    if (execState.latency > 200) { warnings.push("HIGH LATENCY"); return 0.2; }
    if (execState.latency > 100) return 0.5;
    return 0.85;
  })();

  const rrQuality = (() => {
    if (alphaState.sharpe > 1.5) return 0.9;
    if (alphaState.sharpe > 1) return 0.7;
    if (alphaState.sharpe > 0.5) return 0.45;
    return 0.2;
  })();

  const rawScore = (
    regimeAlignment * 0.25 +
    volSuitability * 0.2 +
    trendStrength * 0.15 +
    liquidityScore * 0.1 +
    correlationEnv * 0.05 +
    executionConditions * 0.1 +
    rrQuality * 0.15
  );
  const entryScore = Math.max(0, rawScore * (1 - htfPenalty));
  if (htfPenalty > 0.15) warnings.push(`HTF CONFLICT (-${(htfPenalty * 100).toFixed(0)}%)`);

  const confidenceScore = (state?.confidence ?? 0.5) * (alphaState.signalStability);
  const regimeConfidence = state?.confidence ?? 0.5;

  let signalsSuppressed = false;
  if (riskState.drawdownPct > 3) { signalsSuppressed = true; suppressionReasons.push("DRAWDOWN EXCEEDS 3%"); }
  if (riskState.propProximity > 60) { signalsSuppressed = true; suppressionReasons.push("PROP FIRM PROXIMITY >60%"); }
  if (riskState.leverage > 4) { signalsSuppressed = true; suppressionReasons.push("LEVERAGE TOO HIGH"); }
  if (market.crisis_probability && probFraction(market.crisis_probability) > 0.4) {
    signalsSuppressed = true;
    suppressionReasons.push("CRISIS PROBABILITY >40%");
  }
  if (htfPenalty > 0.3) { signalsSuppressed = true; suppressionReasons.push("STRONG HTF CONFLICT"); }

  const qualityRating: EntryQuality["quality_rating"] =
    signalsSuppressed ? "AVOID" :
    entryScore > 0.7 ? "HIGH_QUALITY" :
    entryScore > 0.5 ? "ACCEPTABLE" :
    entryScore > 0.3 ? "LOW_EDGE" : "AVOID";

  if (qualityRating === "AVOID") warnings.push("SIGNALS SUPPRESSED");

  return {
    entry_score: entryScore,
    confidence_score: confidenceScore,
    regime_confidence: regimeConfidence,
    quality_rating: qualityRating,
    regime_alignment: regimeAlignment,
    volatility_suitability: volSuitability,
    trend_strength_score: trendStrength,
    liquidity_score: liquidityScore,
    correlation_environment: correlationEnv,
    execution_conditions: executionConditions,
    risk_reward_quality: rrQuality,
    warnings,
    signals_suppressed: signalsSuppressed,
    suppression_reasons: suppressionReasons,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SHARED SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────────────────

function Divider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 my-1">
      <div className="flex-1 h-px" style={{ background: C.border }} />
      {label && <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.15em" }}>{label}</span>}
      <div className="flex-1 h-px" style={{ background: C.border }} />
    </div>
  );
}

function StatRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-baseline justify-between py-[2px]">
      <span style={{ fontSize: 9, color: C.t2, letterSpacing: "0.04em" }}>{label}</span>
      <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, color: accent ?? C.t1 }}>{value}</span>
    </div>
  );
}

function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div className="flex items-center gap-2">
      <span style={{ fontSize: 8, color: C.t2, width: 60, letterSpacing: "0.04em", flexShrink: 0 }}>{label}</span>
      <div className="flex-1 h-[3px]" style={{ background: C.border }}>
        <div className="h-full transition-all duration-300" style={{ width: `${pct * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", color: C.t1, width: 28, textAlign: "right" }}>
        {(pct * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function RegimeDot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <div className="relative flex items-center justify-center w-3 h-3">
      {pulse && <div className="absolute w-3 h-3 rounded-full animate-ping opacity-50" style={{ background: color }} />}
      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
    </div>
  );
}

function LegendPill({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-[5px]">
      <div className="w-4 h-[2px] rounded-full" style={{ background: color }} />
      <span style={{ fontSize: 9, color: C.t2, letterSpacing: "0.04em" }}>{label}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ENTRY QUALITY OVERLAY — real-time trade quality score on chart
// ─────────────────────────────────────────────────────────────────────────────

function EntryQualityOverlay({ quality }: { quality: EntryQuality }) {
  const ratingColors: Record<string, string> = {
    HIGH_QUALITY: C.bullish,
    ACCEPTABLE: C.cyan,
    LOW_EDGE: C.volatile,
    AVOID: C.critical,
  };
  const color = ratingColors[quality.quality_rating] ?? C.neutral;

  const ratingLabels: Record<string, string> = {
    HIGH_QUALITY: "HIGH QUALITY SETUP",
    ACCEPTABLE: "ACCEPTABLE ENTRY",
    LOW_EDGE: "LOW EDGE ENVIRONMENT",
    AVOID: "AVOID — SIGNALS SUPPRESSED",
  };

  return (
    <div
      className="absolute top-4 left-[240px] z-50 w-[200px]"
      style={{
        background: "rgba(8,8,9,0.96)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${color}`,
        padding: "10px 12px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>ENTRY QUALITY</span>
        <RegimeDot color={color} pulse={quality.quality_rating === "HIGH_QUALITY"} />
      </div>

      <div style={{ fontSize: 11, fontWeight: 700, color, lineHeight: 1.2, marginBottom: 4, letterSpacing: "0.02em" }}>
        {ratingLabels[quality.quality_rating]}
      </div>

      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mb-2">
        <StatRow label="SCORE" value={`${(quality.entry_score * 100).toFixed(0)}`} accent={color} />
        <StatRow label="CONFIDENCE" value={fmtPct(quality.confidence_score)} accent={quality.confidence_score > 0.6 ? C.bullish : C.warning} />
      </div>

      <Divider label="FACTORS" />
      <div className="space-y-1">
        <ProbBar label="REGIME" value={quality.regime_alignment} color={C.cyan} />
        <ProbBar label="VOL SUIT" value={quality.volatility_suitability} color={C.volatile} />
        <ProbBar label="TREND" value={quality.trend_strength_score} color={C.bullish} />
        <ProbBar label="LIQUIDITY" value={quality.liquidity_score} color={C.blue} />
        <ProbBar label="EXECUTION" value={quality.execution_conditions} color={C.purple} />
        <ProbBar label="R/R QUAL" value={quality.risk_reward_quality} color={C.amber} />
      </div>

      {quality.warnings.length > 0 && (
        <>
          <Divider label="WARNINGS" />
          {quality.warnings.map((w, i) => (
            <div key={i} style={{ fontSize: 8, color: C.danger, letterSpacing: "0.06em", lineHeight: 1.4 }}>
              ⚠ {w}
            </div>
          ))}
        </>
      )}

      {quality.signals_suppressed && (
        <div className="mt-1 px-1 py-0.5" style={{ background: "rgba(220,38,38,0.1)", borderLeft: `2px solid ${C.critical}` }}>
          {quality.suppression_reasons.map((r, i) => (
            <div key={i} style={{ fontSize: 7, color: C.critical, letterSpacing: "0.05em" }}>{r}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// REGIME INTELLIGENCE OVERLAY (enhanced)
// ─────────────────────────────────────────────────────────────────────────────

function RegimeIntelligenceOverlay({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const rColor = regimeColor(state?.market_regime ?? market.hmm_regime);
  const dColor = state?.direction?.toUpperCase().includes("BULL") ? C.bullish : state?.direction?.toUpperCase().includes("BEAR") ? C.bearish : C.neutral;
  const isActive = ["TRENDING", "STRONG", "EXTREME"].includes(state?.trend_strength ?? "");

  const strengthMap: Record<string, string> = { CHOPPY: "RANGING", WEAK: "WEAK TREND", TRENDING: "TRENDING", STRONG: "STRONG", EXTREME: "EXTREME" };

  return (
    <div
      className="absolute top-4 left-4 z-50 w-[220px]"
      style={{
        background: "rgba(8,8,9,0.96)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${rColor}`,
        padding: "10px 12px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>REGIME ENGINE</span>
        <RegimeDot color={rColor} pulse={isActive} />
      </div>

      <div style={{ fontSize: 18, fontWeight: 700, color: rColor, lineHeight: 1.1, letterSpacing: "-0.02em", marginBottom: 2 }}>
        {strengthMap[state?.trend_strength ?? ""] ?? "--"}
      </div>
      <div style={{ fontSize: 9, color: C.t2, marginBottom: 6 }}>
        {state?.market_regime?.replace(/_/g, " ") ?? "--"}
      </div>

      <Divider label="DIRECTIONAL" />
      <div className="space-y-[1px]">
        <StatRow label="REGIME" value={state?.market_regime ?? "--"} accent={rColor} />
        <StatRow label="DIRECTION" value={state?.direction ?? "--"} accent={dColor} />
        <StatRow label="ADX" value={state?.adx?.toFixed(2) ?? "--"} accent={rColor} />
        <StatRow label="+DI / −DI" value={`${fmt(state?.plus_di)} / ${fmt(state?.minus_di)}`} accent={C.t1} />
      </div>

      <Divider label="HMM POSTERIOR" />
      <div className="space-y-[4px]">
        <ProbBar label="MEAN-REV" value={probFraction(market.mean_revert_probability)} color={C.cyan} />
        <ProbBar label="TRENDING" value={probFraction(market.trend_probability)} color={C.bullish} />
        <ProbBar label="CRISIS" value={probFraction(market.crisis_probability)} color={C.crisis} />
        {market.bull_probability != null && (
          <ProbBar label="BULL" value={probFraction(market.bull_probability)} color={C.bullish} />
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// VOLATILITY STATE OVERLAY (enhanced)
// ─────────────────────────────────────────────────────────────────────────────

function VolatilityStateOverlay({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const volRegime = state?.volatility_regime ?? market.vol_regime ?? "--";
  const volColor = regimeColor(volRegime);

  const garchDisplay = state?.volatility != null ? `${fmt(state.volatility)}%` :
    market.garch_vol != null ? fmt(market.garch_vol, 4) : "--";

  return (
    <div
      className="absolute top-4 right-4 z-50 w-[190px]"
      style={{
        background: "rgba(8,8,9,0.96)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${volColor}`,
        padding: "10px 12px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>VOL SURFACE</span>
        <RegimeDot color={volColor} />
      </div>

      <div style={{ fontSize: 16, fontWeight: 700, color: volColor, lineHeight: 1.1, marginBottom: 2 }}>
        {volRegime}
      </div>
      <div style={{ fontSize: 8, color: C.t2, marginBottom: 6 }}>GARCH CONDITIONAL VOL</div>

      <Divider />
      <div className="space-y-[1px]">
        <StatRow label="σ (GARCH)" value={garchDisplay} accent={volColor} />
        <StatRow label="TRANS. RISK" value={state?.transition_risk ?? "--"} accent={state?.transition_risk === "ELEVATED" ? C.bearish : C.t1} />
        <StatRow label="PERSISTENCE" value={state?.trend_persistence ?? "--"} accent={state?.trend_persistence === "WEAK" ? C.volatile : state?.trend_persistence === "STRONG" ? C.bullish : C.t1} />
        <StatRow label="RISK STATE" value={state?.risk_state ?? "--"} />
        <StatRow label="CONFIDENCE" value={state?.confidence != null ? fmtPct(state.confidence) : "--"} accent={(state?.confidence ?? 0) > 0.75 ? C.bullish : (state?.confidence ?? 0) > 0.5 ? C.volatile : C.bearish} />
      </div>

      <Divider label="VOL EXPANSION PROB" />
      <ProbBar label="EXPAND" value={volRegime.includes("EXPAND") ? 0.75 : 0.25} color={C.volatile} />
      <ProbBar label="COMPRESS" value={volRegime.includes("COMPRESS") ? 0.7 : 0.3} color={C.cyan} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTION QUALITY OVERLAY
// ─────────────────────────────────────────────────────────────────────────────

function ExecutionQualityOverlay() {
  const slip = useExecutionStore((s) => s.slippage);
  const lat = useExecutionStore((s) => s.latency);
  const bh = useExecutionStore((s) => s.brokerHealth);

  const execScore = (() => {
    let score = 1;
    if (slip.avg_slippage_bps > 5) score -= 0.4;
    else if (slip.avg_slippage_bps > 2) score -= 0.15;
    if (lat.p99_latency_ms > 200) score -= 0.3;
    else if (lat.p99_latency_ms > 100) score -= 0.1;
    if (bh.api_status !== "CONNECTED") score -= 0.3;
    return Math.max(0, score);
  })();

  const execColor = execScore > 0.7 ? C.safe : execScore > 0.4 ? C.warning : C.danger;
  const execLabel = execScore > 0.7 ? "OPTIMAL" : execScore > 0.4 ? "DEGRADED" : "POOR";

  return (
    <div
      className="absolute bottom-12 right-4 z-40 w-[170px]"
      style={{
        background: "rgba(8,8,9,0.94)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${execColor}`,
        padding: "8px 10px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>EXEC QUALITY</span>
        <RegimeDot color={execColor} />
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: execColor, marginBottom: 4 }}>{execLabel}</div>
      <div className="space-y-[1px]">
        <StatRow label="SLIPPAGE" value={`${fmt(slip.avg_slippage_bps, 1)}bps`} accent={slip.avg_slippage_bps > 3 ? C.danger : C.t1} />
        <StatRow label="P99 LAT" value={`${fmt(lat.p99_latency_ms, 0)}ms`} accent={lat.p99_latency_ms > 200 ? C.danger : C.t1} />
        <StatRow label="BROKER" value={bh.api_status} accent={bh.api_status === "CONNECTED" ? C.safe : C.danger} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ALPHA HEALTH OVERLAY
// ─────────────────────────────────────────────────────────────────────────────

function AlphaHealthOverlay() {
  const alpha = useAlphaStore((s) => s.alpha);
  const healthColor = alpha.rolling_sharpe_trend === "DETERIORATING" ? C.danger :
    alpha.rolling_sharpe > 1 ? C.safe : C.warning;

  return (
    <div
      className="absolute bottom-12 left-4 z-40 w-[170px]"
      style={{
        background: "rgba(8,8,9,0.94)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${healthColor}`,
        padding: "8px 10px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>ALPHA HEALTH</span>
        <RegimeDot color={healthColor} pulse={alpha.rolling_sharpe_trend === "DETERIORATING"} />
      </div>
      <div style={{ fontSize: 12, fontWeight: 700, color: healthColor, marginBottom: 4 }}>
        SR {fmt(alpha.rolling_sharpe)} {alpha.rolling_sharpe_trend === "DETERIORATING" ? "↓" : alpha.rolling_sharpe_trend === "IMPROVING" ? "↑" : "→"}
      </div>
      <div className="space-y-[1px]">
        <StatRow label="WINRATE 7D" value={`${fmt(alpha.winrate_7d, 1)}%`} accent={alpha.winrate_7d > 55 ? C.bullish : C.warning} />
        <StatRow label="STABILITY" value={alpha.winrate_stability} accent={alpha.winrate_stability === "STABLE" ? C.safe : C.danger} />
        <StatRow label="EDGE REL" value={fmt(alpha.edge_reliability)} accent={alpha.edge_reliability > 0.6 ? C.safe : C.danger} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CHART LEGEND BAR
// ─────────────────────────────────────────────────────────────────────────────

function ChartLegendBar() {
  return (
    <div
      className="absolute bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-4"
      style={{
        background: "rgba(8,8,9,0.88)",
        border: `1px solid ${C.border}`,
        padding: "4px 10px",
      }}
    >
      <LegendPill color={C.candleUp} label="PRICE" />
      <LegendPill color={C.ema20} label="EMA 20" />
      <LegendPill color={C.ema50} label="EMA 50" />
      <LegendPill color={C.volatile} label="GARCH" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN CHART COMPONENT
// ─────────────────────────────────────────────────────────────────────────────

export default function MainChart({ market }: { market: MarketPayload }) {
  const containerRef = useRef<HTMLDivElement>(null);

  const dd = useRiskStore((s) => s.drawdown);
  const pf = useRiskStore((s) => s.propFirm);
  const risk = useRiskStore((s) => s.portfolioRisk);
  const alpha = useAlphaStore((s) => s.alpha);
  const slip = useExecutionStore((s) => s.slippage);
  const lat = useExecutionStore((s) => s.latency);
  const htfPenalty = useTimeframeStore((s) => s.alignment.htf_conflict_penalty);
  const activeTF = useTimeframeStore((s) => s.activeTimeframe);
  const tfLoading = useTimeframeStore((s) => s.loadingTimeframes);

  const entryQuality = useMemo(() => computeEntryQuality(
    market,
    { drawdownPct: Math.abs(dd.daily_drawdown), propProximity: Math.max(pf.daily_proximity_pct, pf.max_proximity_pct), leverage: risk.leverage },
    { sharpe: alpha.rolling_sharpe, winrate7d: alpha.winrate_7d, signalStability: alpha.signal_stability },
    { avgSlippage: slip.avg_slippage_bps, latency: lat.p99_latency_ms },
    htfPenalty,
  ), [market, dd, pf, risk, alpha, slip, lat, htfPenalty]);

  useEffect(() => {
    if (!containerRef.current || !market?.chart_data?.length) return;

    const isIntraday = typeof market.chart_data[0]?.time === "number";

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
      height: 640,
      rightPriceScale: {
        borderColor: C.border,
        textColor: C.t2,
        minimumWidth: 64,
      },
      timeScale: {
        borderColor: C.border,
        timeVisible: isIntraday,
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

    // Regime background overlays
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

    const trendOverlay = makeOverlay("rgba(34,197,94,0.07)");
    const volOverlay = makeOverlay("rgba(245,158,11,0.07)");
    const crisisOverlay = makeOverlay("rgba(239,68,68,0.07)");

    const ema20Series = chart.addSeries(LineSeries, { color: C.ema20, lineWidth: 1, lastValueVisible: false, priceLineVisible: false });
    const ema50Series = chart.addSeries(LineSeries, { color: C.ema50, lineWidth: 1, lastValueVisible: false, priceLineVisible: false });

    const volHistogram = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol" });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    const transitionSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol" });

    // Data mapping — cast time to satisfy lightweight-charts branded Time type
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const t = (v: string | number): any => v;

    const candles = market.chart_data.map((b) => ({ time: t(b.time), open: finiteNum(b.open), high: finiteNum(b.high), low: finiteNum(b.low), close: finiteNum(b.close) }));
    const ema20Data = market.chart_data.map((b) => ({ time: t(b.time), value: finiteNum(b.ema20) }));
    const ema50Data = market.chart_data.map((b) => ({ time: t(b.time), value: finiteNum(b.ema50) }));

    const trendBars = market.chart_data.filter((b) => b.hmm_regime === "TRENDING");
    const volBars = market.chart_data.filter((b) => b.hmm_regime === "MEAN_REVERT");
    const crisisBars = market.chart_data.filter((b) => b.hmm_regime === "CRISIS");
    const toOverlay = (bars: typeof market.chart_data) => bars.map((b) => ({ time: t(b.time), value: b.close }));

    const volHistData = market.chart_data.map((b) => ({
      time: t(b.time),
      value: finiteNum(b.garch_vol),
      color: finiteNum(b.close) > finiteNum(b.open) ? "rgba(34,197,94,0.40)" : "rgba(239,68,68,0.40)",
    }));

    const transitionData = market.chart_data.map((b, idx) => {
      const prev = market.chart_data[idx - 1];
      const isTransition = prev && ((b.hmm_regime && prev.hmm_regime !== b.hmm_regime) || (b.direction && prev.direction !== b.direction));
      return {
        time: t(b.time),
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

    // Markers — only show if signals not suppressed
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const markers: any[] = [];

    if (!entryQuality.signals_suppressed) {
      market.chart_data.forEach((b, idx) => {
        const prev = market.chart_data[idx - 1];
        if (!prev) return;
        const dirChanged = b.direction && prev.direction && b.direction !== prev.direction;
        const hmmChanged = b.hmm_regime && prev.hmm_regime && b.hmm_regime !== prev.hmm_regime;
        if (!dirChanged && !hmmChanged) return;

        const dir = (b.direction ?? "").toUpperCase();
        if (dir.includes("BULL")) {
          markers.push({ time: t(b.time), position: "belowBar", color: C.bullish, shape: "arrowUp", text: "BULL REGIME", size: 1 });
        } else if (dir.includes("BEAR")) {
          markers.push({ time: t(b.time), position: "aboveBar", color: C.bearish, shape: "arrowDown", text: "BEAR REGIME", size: 1 });
        } else if (b.hmm_regime === "CRISIS" || hmmChanged) {
          markers.push({ time: t(b.time), position: "aboveBar", color: C.volatile, shape: "circle", text: "REGIME BREAK", size: 1 });
        }
      });
    }

    if (markers.length) createSeriesMarkers(candleSeries, markers);

    const handleResize = () => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); chart.remove(); };
  }, [market, entryQuality.signals_suppressed]);

  return (
    <div className="relative w-full" style={{ background: C.bg, fontFamily: "'IBM Plex Sans', sans-serif" }}>
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 11, fontWeight: 700, color: C.t1, letterSpacing: "0.08em", fontFamily: "'IBM Plex Mono', monospace" }}>
            {market.symbol?.replace("-", " / ") ?? "BTC / USD"}
          </span>
          <span style={{ fontSize: 8, color: C.t3, background: C.surface, border: `1px solid ${C.border}`, padding: "1px 5px", letterSpacing: "0.1em" }}>
            {activeTF}
          </span>
          {tfLoading.includes(activeTF) && (
            <span className="animate-pulse" style={{ fontSize: 8, color: C.volatile, letterSpacing: "0.1em" }}>LOADING...</span>
          )}
          <div className="h-3 w-px" style={{ background: C.border }} />
          <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.06em" }}>MULTI-TIMEFRAME DECISION ENGINE</span>
        </div>
        <div className="flex items-center gap-4">
          <LegendPill color={C.ema20} label="EMA 20" />
          <LegendPill color={C.ema50} label="EMA 50" />
          <div className="h-3 w-px" style={{ background: C.border }} />
          <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.1em", fontFamily: "'IBM Plex Mono', monospace" }}>
            ADX-14 · GARCH · HMM-3S
          </span>
        </div>
      </div>

      {/* Chart + overlays */}
      <div className="relative">
        <div ref={containerRef} className="w-full" />
        <RegimeIntelligenceOverlay market={market} />
        <EntryQualityOverlay quality={entryQuality} />
        <VolatilityStateOverlay market={market} />
        <MTFAlignmentOverlay />
        <ExecutionQualityOverlay />
        <AlphaHealthOverlay />
        <ChartLegendBar />
      </div>
    </div>
  );
}
