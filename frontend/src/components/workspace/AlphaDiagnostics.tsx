"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  ProgressBar,
  StatusBadge,
  Divider,
  Sparkline,
  AlertStrip,
} from "@/components/ui/primitives";
import { useAlphaStore } from "@/state/stores/useAlphaStore";

function trendColor(trend: string): string {
  if (trend === "IMPROVING") return C.bullish;
  if (trend === "DETERIORATING") return C.danger;
  return C.t1;
}

function stabilityColor(s: string): string {
  if (s === "STABLE") return C.safe;
  if (s === "UNSTABLE") return C.warning;
  return C.danger;
}

function SharpePanel() {
  const alpha = useAlphaStore((s) => s.alpha);

  return (
    <Panel label="ROLLING SHARPE" accent={alpha.rolling_sharpe > 1 ? C.bullish : C.warning}>
      <div className="flex items-center gap-4 mb-2">
        <div
          style={{
            fontSize: 28,
            fontFamily: "'IBM Plex Mono', monospace",
            fontWeight: 800,
            color: alpha.rolling_sharpe > 1 ? C.bullish : alpha.rolling_sharpe > 0.5 ? C.warning : C.danger,
            letterSpacing: "-0.03em",
          }}
        >
          {fmt(alpha.rolling_sharpe)}
        </div>
        <StatusBadge label={alpha.rolling_sharpe_trend} color={trendColor(alpha.rolling_sharpe_trend)} pulse={alpha.rolling_sharpe_trend === "DETERIORATING"} />
      </div>
      <Divider label="PnL (RECENT 15)" />
      <Sparkline data={alpha.recent_pnl} width={200} height={28} color={C.bullish} />
      {alpha.rolling_sharpe_trend === "DETERIORATING" && (
        <div className="mt-2">
          <AlertStrip text="SHARPE RATIO DETERIORATING — ALPHA QUALITY AT RISK" severity="warning" />
        </div>
      )}
    </Panel>
  );
}

function AlphaDecayPanel() {
  const alpha = useAlphaStore((s) => s.alpha);

  return (
    <Panel label="ALPHA DECAY ANALYSIS" accent={C.purple}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="IC DECAY" value={fmt(alpha.ic_decay, 3)} accent={alpha.ic_decay > 0.05 ? C.danger : C.t1} large />
        <StatCell label="ALPHA DECAY" value={`${fmt(alpha.alpha_decay_rate * 100)}%/d`} accent={alpha.alpha_decay_rate > 0.03 ? C.danger : C.t1} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="SIGNAL STABILITY" value={fmt(alpha.signal_stability)} accent={alpha.signal_stability > 0.7 ? C.safe : C.danger} />
        <StatRow label="EDGE RELIABILITY" value={fmt(alpha.edge_reliability)} accent={alpha.edge_reliability > 0.6 ? C.safe : C.danger} />
        <StatRow label="FEATURE DRIFT" value={fmt(alpha.feature_drift)} accent={alpha.feature_drift > 0.15 ? C.danger : C.t1} />
      </div>
      {alpha.feature_drift > 0.15 && (
        <div className="mt-2">
          <AlertStrip text="FEATURE DRIFT DETECTED — RECALIBRATION MAY BE NEEDED" severity="warning" />
        </div>
      )}
    </Panel>
  );
}

function WinratePanel() {
  const alpha = useAlphaStore((s) => s.alpha);

  return (
    <Panel label="WINRATE STABILITY" accent={stabilityColor(alpha.winrate_stability)}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="30D WINRATE" value={`${fmt(alpha.winrate_30d, 1)}%`} accent={alpha.winrate_30d > 55 ? C.bullish : C.warning} large />
        <StatCell label="7D WINRATE" value={`${fmt(alpha.winrate_7d, 1)}%`} accent={alpha.winrate_7d > 55 ? C.bullish : C.warning} large />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ fontSize: 9, color: C.t3 }}>STABILITY</span>
        <StatusBadge label={alpha.winrate_stability} color={stabilityColor(alpha.winrate_stability)} />
      </div>
      <Divider label="TRADE DISTRIBUTION" />
      <div className="space-y-0.5">
        <ProgressBar label="LONG" value={alpha.trade_distribution.long_pct} color={C.bullish} max={100} />
        <ProgressBar label="SHORT" value={alpha.trade_distribution.short_pct} color={C.bearish} max={100} />
        <StatRow label="AVG HOLD" value={`${fmt(alpha.trade_distribution.avg_hold_hours, 1)}h`} />
      </div>
    </Panel>
  );
}

function RegimePerformancePanel() {
  const alpha = useAlphaStore((s) => s.alpha);
  const regimes = Object.entries(alpha.regime_performance);

  return (
    <Panel label="REGIME PERFORMANCE" accent={C.cyan}>
      <div className="space-y-0.5">
        {regimes.map(([regime, perf]) => (
          <div key={regime} className="flex items-center justify-between py-0.5 px-1"
            style={{
              borderLeft: `2px solid ${regimeColor(regime)}`,
              background: perf < 0 ? "rgba(239,68,68,0.04)" : "transparent",
            }}
          >
            <span style={{ fontSize: 10, color: regimeColor(regime), letterSpacing: "0.04em" }}>
              {regime.replace(/_/g, " ")}
            </span>
            <span style={{
              fontSize: 11,
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 700,
              color: perf >= 0 ? C.bullish : C.bearish,
            }}>
              {perf >= 0 ? "+" : ""}{fmt(perf)}%
            </span>
          </div>
        ))}
      </div>
      <Divider />
      <div style={{ fontSize: 9, color: C.t3 }}>
        Performance attribution by HMM regime state. Negative regimes indicate strategy underperformance.
      </div>
    </Panel>
  );
}

export default function AlphaDiagnostics() {
  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <SharpePanel />
        </div>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <AlphaDecayPanel />
        </div>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <WinratePanel />
        </div>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <RegimePerformancePanel />
        </div>
      </div>
    </div>
  );
}
