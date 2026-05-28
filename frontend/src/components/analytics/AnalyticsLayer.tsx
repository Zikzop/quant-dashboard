"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import { fmt } from "@/lib/format";
import { Collapsible } from "@/components/ui/Collapsible";
import { StatRow, Divider, AlertStrip, StatCell } from "@/components/ui/primitives";
import { CalibratedProbBar } from "./CalibratedProbBar";
import CrossAssetHeatmap from "@/components/quant/CrossAssetHeatmap";
import {
  useDisclosureStore,
  type AnalyticsPanelId,
} from "@/state/stores/useDisclosureStore";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import type { MarketPayload } from "@/types/market";
import type { DecisionState } from "@/engines/types";

// ─────────────────────────────────────────────────────────────────────────────
// LEVEL 2 — ANALYTICS LAYER
//
// Collapsible, expand-on-demand panels. Each header carries a compact summary so
// the section stays scannable while collapsed (progressive disclosure).
// ─────────────────────────────────────────────────────────────────────────────

function MiniLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label, marginBottom: 6 }}>
      {children}
    </div>
  );
}

// ── PROBABILISTIC DECOMPOSITION ────────────────────────────────────────────────
function ProbabilityBody({ d }: { d: DecisionState }) {
  const p = d.probability;
  return (
    <div>
      <MiniLabel>DIRECTIONAL (CALIBRATED · CI BANDS · RAW GHOST)</MiniLabel>
      <div className="space-y-1.5">
        <CalibratedProbBar label="BULL" prob={p.bull} color={C.bullish} />
        <CalibratedProbBar label="BEAR" prob={p.bear} color={C.bearish} />
      </div>
      <Divider label="REGIME STATE (CALIBRATED)" />
      <div className="space-y-1.5">
        <CalibratedProbBar label="TREND CONT" prob={p.trend} color={C.bullish} />
        <CalibratedProbBar label="MEAN REVERT" prob={p.meanRevert} color={C.cyan} />
        <CalibratedProbBar label="CRISIS" prob={p.crisis} color={C.critical} />
      </div>
      <Divider label="CALIBRATION" />
      <div className="grid grid-cols-3 gap-1">
        <StatCell label="METHOD" value={p.diagnostics.method === "isotonic+platt+bayes" ? "ISO+PLATT" : p.diagnostics.method === "platt+bayes" ? "PLATT" : "BAYES"} accent={C.cyan} />
        <StatCell label="SAMPLES" value={`${p.diagnostics.sampleSize}`} accent={p.diagnostics.sampleSize > 40 ? C.bullish : C.warning} />
        <StatCell label="DISPERSION" value={`${(p.dispersion * 100).toFixed(0)}%`} accent={p.dispersion > 0.6 ? C.warning : C.t1} />
      </div>
      <div className="mt-2">
        <StatRow
          label="MAX SHRINKAGE"
          value={`${(Math.max(Math.abs(p.bull.shrinkage), Math.abs(p.crisis.shrinkage)) * 100).toFixed(0)}pp`}
          accent={C.amber}
          sub="raw→calibrated"
        />
      </div>
    </div>
  );
}

// ── REGIME TRANSITION ───────────────────────────────────────────────────────────
function TransitionBody({ d }: { d: DecisionState }) {
  const t = d.transition;
  if (!t.available) {
    return <span style={{ fontSize: T.sm, color: C.t3 }}>Transition matrix unavailable.</span>;
  }
  const stabColor = t.stability === "STABLE" ? C.bullish : t.stability === "FRAGILE" ? C.warning : C.danger;
  return (
    <div>
      <div className="flex items-stretch gap-2 mb-2">
        <div className="flex-1" style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "8px 10px" }}>
          <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>CURRENT REGIME</div>
          <div style={{ fontSize: T.lg, fontWeight: 700, color: regimeColor(t.current), letterSpacing: TRACK.value }}>
            {t.current.replace(/_/g, " ")}
          </div>
          <div style={{ fontSize: T.pico, color: C.t3, marginTop: 2 }}>
            PERSIST {(t.persistence * 100).toFixed(0)}% · DWELL {t.expectedDurationBars != null ? `${t.expectedDurationBars.toFixed(1)}b` : "--"}
          </div>
        </div>
        <div className="flex items-center justify-center" style={{ width: 28, color: C.t3, fontSize: T.md }}>→</div>
        <div className="flex-1" style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "8px 10px" }}>
          <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>LIKELY NEXT</div>
          <div style={{ fontSize: T.lg, fontWeight: 700, color: regimeColor(t.mostLikelyNext?.to ?? ""), letterSpacing: TRACK.value }}>
            {t.mostLikelyNext ? t.mostLikelyNext.to.replace(/_/g, " ") : "--"}
          </div>
          <div style={{ fontSize: T.pico, color: C.t3, marginTop: 2 }}>
            P(TRANSITION) {(t.transitionProbability * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <MiniLabel>TRANSITION PROBABILITIES (NEXT STEP)</MiniLabel>
      <div className="space-y-1">
        {t.nextRegimes.slice(0, 4).map((edge) => (
          <div key={edge.to} className="flex items-center gap-2">
            <span style={{ fontSize: T.nano, color: regimeColor(edge.to), width: 84, flexShrink: 0, fontWeight: 600 }}>
              {edge.to.replace(/_/g, " ")}
            </span>
            <div className="flex-1 h-[5px]" style={{ background: C.border }}>
              <div className="h-full" style={{ width: `${edge.probability * 100}%`, background: regimeColor(edge.to), opacity: 0.7 }} />
            </div>
            <span style={{ fontSize: T.nano, fontFamily: "'IBM Plex Mono', monospace", color: C.t2, width: 34, textAlign: "right" }}>
              {(edge.probability * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      <Divider label="STABILITY" />
      <div className="flex items-center justify-between">
        <StatRow label="TRANSITION INSTABILITY" value={`${(t.instability * 100).toFixed(0)}%`} accent={stabColor} />
      </div>
      <StatRow label="REGIME STABILITY" value={t.stability} accent={stabColor} />
      {t.lowConfidence && (
        <div className="mt-1.5">
          <AlertStrip text="LOW-CONFIDENCE TRANSITION ESTIMATE — SPARSE HISTORY" severity="warning" />
        </div>
      )}
      {t.stability === "UNSTABLE" && (
        <div className="mt-1.5">
          <AlertStrip text="REGIME UNSTABLE — ELEVATED PROBABILITY OF REGIME SHIFT" severity="danger" />
        </div>
      )}
    </div>
  );
}

// ── EXECUTION QUALITY ───────────────────────────────────────────────────────────
function ExecutionBody({ d }: { d: DecisionState }) {
  const e = d.execution;
  const liqColor = e.liquidity === "DEEP" ? C.bullish : e.liquidity === "NORMAL" ? C.cyan : e.liquidity === "THIN" ? C.warning : C.danger;
  const sessionLabel = e.session.replace(/_/g, " ");
  return (
    <div>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="SESSION" value={sessionLabel} accent={e.sessionQuality > 0.8 ? C.bullish : e.sessionQuality > 0.6 ? C.cyan : C.warning} />
        <StatCell label="LIQUIDITY" value={e.liquidity} accent={liqColor} />
      </div>
      <div className="space-y-0.5">
        <StatRow label="SESSION QUALITY" value={`${(e.sessionQuality * 100).toFixed(0)}%`} accent={C.t1} />
        <StatRow label="EST HALF-SPREAD" value={`${e.spreadBps.toFixed(1)} bps`} accent={C.t1} />
        <StatRow label="EXPECTED SLIPPAGE" value={`${e.expectedSlippageBps.toFixed(1)} bps`} accent={e.expectedSlippageBps > 8 ? C.warning : C.t1} />
        <StatRow label="EXECUTION RISK" value={`${(e.executionRisk * 100).toFixed(0)}%`} accent={e.executionRisk > 0.6 ? C.danger : e.executionRisk > 0.4 ? C.warning : C.bullish} />
        <StatRow label="OPENING DRIVE" value={e.openingDrive ? "ACTIVE" : "NO"} accent={e.openingDrive ? C.warning : C.t2} />
      </div>
      <Divider label="VOLATILITY-ADJUSTED STOP" />
      <div className="flex items-baseline justify-between">
        <span style={{ fontSize: T.sm, color: C.t2 }}>SUGGESTED STOP</span>
        <span style={{ fontSize: T.md, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: C.amber }}>
          {e.volAdjustedStopPct.toFixed(2)}%{e.volAdjustedStopPrice > 0 ? ` · ${e.volAdjustedStopPrice.toFixed(2)}` : ""}
        </span>
      </div>
      {e.warnings.map((w) => (
        <div key={w} className="mt-1.5">
          <AlertStrip text={w} severity={e.executionRisk > 0.6 ? "danger" : "warning"} />
        </div>
      ))}
    </div>
  );
}

// ── RISK ANALYTICS ──────────────────────────────────────────────────────────────
function RiskBody({ d }: { d: DecisionState }) {
  const r = d.risk;
  const tailColor = r.tailRisk === "LOW" ? C.bullish : r.tailRisk === "ELEVATED" ? C.warning : r.tailRisk === "FAT_TAILED" ? C.danger : C.critical;
  return (
    <div>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="VaR 95% (BAR)" value={`${fmt(r.var95)}%`} accent={C.bearish} />
        <StatCell label="CVaR 95%" value={`${fmt(r.cvar95)}%`} accent={C.bearish} />
        <StatCell label="VaR 99%" value={`${fmt(r.var99)}%`} accent={C.critical} />
        <StatCell label="CVaR 99%" value={`${fmt(r.cvar99)}%`} accent={C.critical} />
      </div>
      <div className="space-y-0.5">
        <StatRow label="EXPECTED SHORTFALL" value={`${fmt(r.expectedShortfall)}%`} accent={C.bearish} />
        <StatRow label="REGIME-COND VaR 95%" value={`${fmt(r.regimeConditionedVar95)}%`} accent={r.regimeConditionedVar95 < r.var95 ? C.critical : C.bearish} />
        <StatRow label="ANNUALIZED VOL" value={`${fmt(r.annualizedVol, 1)}%`} accent={C.volatile} />
        <StatRow label="EXCESS KURTOSIS" value={fmt(r.tailKurtosis, 2)} accent={r.tailKurtosis > 3 ? C.danger : C.t1} sub="fat-tail" />
        <StatRow label="SKEW" value={fmt(r.skew, 2)} accent={r.skew < -0.5 ? C.danger : C.t1} />
        <StatRow label="TAIL RISK" value={r.tailRisk.replace(/_/g, " ")} accent={tailColor} />
      </div>
      {r.warnings.map((w) => (
        <div key={w} className="mt-1.5">
          <AlertStrip text={w} severity={r.tailRisk === "EXTREME" ? "critical" : "warning"} />
        </div>
      ))}
    </div>
  );
}

// ── VOLATILITY ANALYTICS ──────────────────────────────────────────────────────
function VolatilityBody({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const volColor = regimeColor(state?.volatility_regime ?? market.vol_regime);
  return (
    <div className="space-y-0.5">
      <StatRow label="REALIZED VOL" value={`${fmt(market.volatility)}%`} accent={C.volatile} />
      <StatRow label="GARCH VOL" value={market.garch_vol != null ? fmt(market.garch_vol, 4) : "--"} accent={C.volatile} />
      <StatRow label="VOL REGIME" value={(market.vol_regime ?? "--").replace(/_/g, " ")} accent={volColor} />
      <StatRow label="VOL SLOPE" value={market.vol_slope != null ? fmt(market.vol_slope, 4) : "--"} accent={(market.vol_slope ?? 0) > 0 ? C.danger : C.safe} sub={(market.vol_slope ?? 0) > 0 ? "expanding" : "contracting"} />
      <StatRow label="RISK STATE" value={(state?.risk_state ?? "--").replace(/_/g, " ")} />
    </div>
  );
}

// ── STRUCTURE ANALYTICS ──────────────────────────────────────────────────────
function StructureBody({ market }: { market: MarketPayload }) {
  const st = market.market_state;
  const dir = (st?.direction ?? "").toUpperCase();
  const dirColor = dir.includes("BULL") ? C.bullish : dir.includes("BEAR") ? C.bearish : C.neutral;
  return (
    <div className="space-y-0.5">
      <StatRow label="DIRECTION" value={st?.direction ?? "--"} accent={dirColor} />
      <StatRow label="TREND STRENGTH" value={st?.trend_strength ?? "--"} accent={regimeColor(st?.trend_strength)} />
      <StatRow label="ADX" value={fmt(st?.adx, 1)} />
      <StatRow label="+DI / −DI" value={`${fmt(st?.plus_di, 0)} / ${fmt(st?.minus_di, 0)}`} />
      <StatRow label="TREND PERSISTENCE" value={st?.trend_persistence ?? "--"} />
      <StatRow label="STRUCTURE REGIME" value={(market.structure_regime ?? "--").replace(/_/g, " ")} accent={regimeColor(market.structure_regime)} />
    </div>
  );
}

// ── HISTORICAL REGIME INTELLIGENCE ──────────────────────────────────────────────
function HistoricalBody() {
  const ctx = useTimeframeStore((s) => s.historicalContext);
  return (
    <div>
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell label="SIMILAR" value={`${ctx.similar_regime_count}`} accent={ctx.similar_regime_count > 3 ? C.bullish : C.warning} />
        <StatCell label="HIST WIN" value={`${fmt(ctx.historical_win_rate, 0)}%`} accent={ctx.historical_win_rate > 55 ? C.bullish : ctx.historical_win_rate > 45 ? C.warning : C.bearish} />
        <StatCell label="AVG RET" value={`${ctx.historical_avg_return >= 0 ? "+" : ""}${fmt(ctx.historical_avg_return)}%`} accent={ctx.historical_avg_return >= 0 ? C.bullish : C.bearish} />
      </div>
      {ctx.regime_stats.length > 0 ? (
        <div className="space-y-1">
          {ctx.regime_stats.slice(0, 5).map((rs) => (
            <div key={rs.regime} className="flex items-center justify-between" style={{ fontSize: T.nano }}>
              <span style={{ color: regimeColor(rs.regime), fontWeight: 600, width: 90 }}>{rs.regime.replace(/_/g, " ")}</span>
              <span style={{ color: C.t3, fontFamily: "'IBM Plex Mono', monospace" }}>WR {fmt(rs.win_rate, 0)}%</span>
              <span style={{ color: rs.avg_return_pct >= 0 ? C.bullish : C.bearish, fontFamily: "'IBM Plex Mono', monospace" }}>
                {rs.avg_return_pct >= 0 ? "+" : ""}{fmt(rs.avg_return_pct)}%
              </span>
              <span style={{ color: C.t3, fontFamily: "'IBM Plex Mono', monospace" }}>{rs.occurrences}x</span>
            </div>
          ))}
        </div>
      ) : (
        <span style={{ fontSize: T.sm, color: C.t3 }}>Insufficient historical data.</span>
      )}
      <Divider label="REGIME TIMELINE" />
      <div className="flex gap-px overflow-hidden" style={{ height: 12 }}>
        {ctx.regime_history.slice(-40).map((h, i) => (
          <div key={i} className="flex-1" style={{ background: regimeColor(h.regime), opacity: 0.55, minWidth: 2 }} title={`${h.regime} (${h.duration} bars)`} />
        ))}
      </div>
    </div>
  );
}

// ── CONTAINER ──────────────────────────────────────────────────────────────────
export default function AnalyticsLayer({
  market,
  decision,
}: {
  market: MarketPayload;
  decision: DecisionState;
}) {
  const expanded = useDisclosureStore((s) => s.expanded);
  const toggle = useDisclosureStore((s) => s.togglePanel);
  const expandAll = useDisclosureStore((s) => s.expandAll);
  const collapseAll = useDisclosureStore((s) => s.collapseAll);

  const section = (
    id: AnalyticsPanelId,
    label: string,
    accent: string,
    summary: React.ReactNode,
    body: React.ReactNode,
    tag?: string,
  ) => (
    <Collapsible label={label} accent={accent} open={expanded[id]} onToggle={() => toggle(id)} summary={summary} tag={tag}>
      {body}
    </Collapsible>
  );

  const p = decision.probability;
  const t = decision.transition;
  const e = decision.execution;
  const r = decision.risk;
  const corr = decision.correlation;

  return (
    <div className="flex flex-col" style={{ background: C.bg }}>
      <div
        className="flex items-center justify-between px-3"
        style={{ height: 26, borderBottom: `1px solid ${C.border}`, background: C.surface }}
      >
        <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label, fontWeight: 700 }}>
          ANALYTICS · LEVEL 2
        </span>
        <div className="flex items-center gap-3">
          <button onClick={expandAll} style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.08em", cursor: "pointer" }}>EXPAND ALL</button>
          <button onClick={collapseAll} style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.08em", cursor: "pointer" }}>COLLAPSE</button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-px" style={{ background: C.border }}>
        {section("probability", "PROBABILISTIC DECOMPOSITION", C.bullish,
          `BULL ${(p.bull.calibrated * 100).toFixed(0)}% · CRISIS ${(p.crisis.calibrated * 100).toFixed(0)}%`,
          <ProbabilityBody d={decision} />, p.diagnostics.method === "bayes-only" ? "LOW DATA" : "CALIBRATED")}

        {section("transition", "REGIME TRANSITION ENGINE", C.purple,
          t.available ? `${t.current.replace(/_/g, " ")} → ${t.mostLikelyNext?.to.replace(/_/g, " ") ?? "--"} · ${(t.transitionProbability * 100).toFixed(0)}%` : "unavailable",
          <TransitionBody d={decision} />, t.stability)}

        {section("volatility", "VOLATILITY ANALYTICS", C.volatile,
          `${(market.vol_regime ?? "--").replace(/_/g, " ")} · σ ${fmt(market.volatility, 1)}%`,
          <VolatilityBody market={market} />)}

        {section("structure", "STRUCTURE ANALYTICS", C.cyan,
          `${market.market_state?.direction ?? "--"} · ADX ${fmt(market.market_state?.adx, 0)}`,
          <StructureBody market={market} />)}

        {section("execution", "EXECUTION QUALITY", C.blue,
          `${e.session.replace(/_/g, " ")} · ${e.liquidity} · ${e.expectedSlippageBps.toFixed(1)}bps`,
          <ExecutionBody d={decision} />, e.openingDrive ? "OPEN DRIVE" : undefined)}

        {section("risk", "RISK ANALYTICS", C.danger,
          `CVaR95 ${fmt(r.cvar95)}% · ${r.tailRisk.replace(/_/g, " ")}`,
          <RiskBody d={decision} />, r.tailRisk !== "LOW" ? r.tailRisk.replace(/_/g, " ") : undefined)}

        {section("historical", "HISTORICAL REGIME INTELLIGENCE", C.amber,
          "regime base rates & transitions",
          <HistoricalBody />)}

        {section("correlation", "CROSS-ASSET CORRELATION", C.amber,
          corr.available ? `${corr.regime.replace(/_/g, " ")} · ρ̄ ${corr.meanAbsCorrelation.toFixed(2)}` : "unavailable",
          <CrossAssetHeatmap correlation={market.correlation} />,
          corr.crisisCoupling ? "CRISIS" : undefined)}
      </div>
    </div>
  );
}
