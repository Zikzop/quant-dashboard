"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import { Panel, StatRow, StatCell, Divider, AlertStrip } from "@/components/ui/primitives";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useDecision } from "@/hooks/useDecision";

type ResearchModule = {
  id: string;
  label: string;
  status: "ACTIVE" | "PLACEHOLDER";
  description: string;
};

const MODULES: ResearchModule[] = [
  { id: "cointegration", label: "COINTEGRATION ANALYSIS", status: "PLACEHOLDER", description: "Engle-Granger / Johansen pair tests" },
  { id: "adf", label: "ADF STATIONARITY", status: "PLACEHOLDER", description: "Augmented Dickey-Fuller unit root tests" },
  { id: "hurst", label: "HURST EXPONENT", status: "PLACEHOLDER", description: "Long-memory / mean-reversion persistence" },
  { id: "halflife", label: "HALF-LIFE ANALYSIS", status: "PLACEHOLDER", description: "Ornstein-Uhlenbeck mean-reversion half-life" },
  { id: "walkforward", label: "WALK-FORWARD VALIDATION", status: "PLACEHOLDER", description: "Rolling OOS performance validation" },
  { id: "montecarlo", label: "MONTE CARLO VALIDATION", status: "PLACEHOLDER", description: "Path-dependent risk simulation" },
  { id: "regime_stats", label: "REGIME STATISTICS", status: "ACTIVE", description: "Historical regime base rates & transitions" },
];

function ModuleCard({ mod }: { mod: ResearchModule }) {
  const accent = mod.status === "ACTIVE" ? C.bullish : C.t3;
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        padding: "10px 12px",
        opacity: mod.status === "PLACEHOLDER" ? 0.75 : 1,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span style={{ fontSize: T.micro, fontWeight: 700, color: C.t1, letterSpacing: TRACK.label }}>
          {mod.label}
        </span>
        <span
          style={{
            fontSize: T.pico,
            color: accent,
            letterSpacing: "0.08em",
            fontWeight: 600,
            border: `1px solid ${accent}`,
            padding: "1px 6px",
          }}
        >
          {mod.status}
        </span>
      </div>
      <div style={{ fontSize: T.nano, color: C.t2, lineHeight: 1.4 }}>{mod.description}</div>
    </div>
  );
}

function RegimeStatisticsPanel() {
  const market = useMarketStore((s) => s.market);
  const decision = useDecision(market);

  if (!decision) {
    return (
      <Panel label="REGIME STATISTICS" accent={C.amber}>
        <span style={{ fontSize: T.sm, color: C.t2 }}>Awaiting market data...</span>
      </Panel>
    );
  }

  const t = decision.transition;
  const p = decision.probability;

  return (
    <Panel label="REGIME STATISTICS" accent={C.amber} tag="ACTIVE">
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell label="CURRENT" value={t.current.replace(/_/g, " ")} accent={C.cyan} />
        <StatCell label="PERSIST" value={`${(t.persistence * 100).toFixed(0)}%`} />
        <StatCell label="INSTABILITY" value={`${(t.instability * 100).toFixed(0)}%`} accent={t.instability > 0.4 ? C.danger : C.t1} />
      </div>
      <Divider label="CALIBRATED REGIME PROBABILITIES" />
      <div className="space-y-0.5">
        <StatRow label="TREND" value={`${(p.trend.calibrated * 100).toFixed(1)}%`} accent={C.bullish} />
        <StatRow label="MEAN REVERT" value={`${(p.meanRevert.calibrated * 100).toFixed(1)}%`} accent={C.cyan} />
        <StatRow label="CRISIS" value={`${(p.crisis.calibrated * 100).toFixed(1)}%`} accent={C.danger} />
      </div>
      <Divider label="LIFECYCLE" />
      <div className="space-y-0.5">
        <StatRow label="PHASE" value={decision.lifecycle.phaseLabel} accent={C.amber} />
        <StatRow label="AGE" value={`${decision.lifecycle.regimeAgeBars} bars`} />
        <StatRow
          label="REMAINING"
          value={decision.lifecycle.expectedRemainingBars != null ? `${decision.lifecycle.expectedRemainingBars.toFixed(0)} bars` : "--"}
        />
      </div>
      {t.lowConfidence && (
        <div className="mt-2">
          <AlertStrip text="LOW-CONFIDENCE TRANSITION ESTIMATE" severity="warning" />
        </div>
      )}
    </Panel>
  );
}

function CalibrationDiagnosticsPanel() {
  const market = useMarketStore((s) => s.market);
  const decision = useDecision(market);

  if (!decision) return null;
  const d = decision.probability.diagnostics;

  return (
    <Panel label="PROBABILITY CALIBRATION" accent={C.purple} tag={d.method.toUpperCase()}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="SAMPLES" value={`${d.sampleSize}`} />
        <StatCell label="HORIZON" value={`${d.horizonBars}b`} />
        <StatCell label="BRIER RAW" value={d.brierRaw != null ? d.brierRaw.toFixed(3) : "--"} />
        <StatCell label="BRIER CAL" value={d.brierCalibrated != null ? d.brierCalibrated.toFixed(3) : "--"} />
      </div>
      <Divider label="DISPERSION & SHRINKAGE" />
      <StatRow label="DISPERSION" value={`${(decision.probability.dispersion * 100).toFixed(0)}%`} />
      <StatRow label="MAX SHRINKAGE" value={`${(Math.max(Math.abs(decision.probability.bull.shrinkage), Math.abs(decision.probability.crisis.shrinkage)) * 100).toFixed(0)}pp`} />
    </Panel>
  );
}

export default function ResearchWorkspace() {
  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div
        className="flex items-center justify-between px-4"
        style={{ height: 32, borderBottom: `1px solid ${C.border}`, background: C.surface }}
      >
        <span style={{ fontSize: T.micro, color: C.t1, letterSpacing: TRACK.label, fontWeight: 700 }}>
          QUANTITATIVE RESEARCH WORKSPACE
        </span>
        <span style={{ fontSize: T.pico, color: C.t3, letterSpacing: "0.08em" }}>
          VALIDATION · STATISTICS · INFRASTRUCTURE
        </span>
      </div>

      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12 lg:col-span-8" style={{ background: C.bg }}>
          <div className="p-2">
            <div style={{ fontSize: T.nano, color: C.t2, letterSpacing: TRACK.label, marginBottom: 8, fontWeight: 700 }}>
              RESEARCH MODULES
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-px" style={{ background: C.border }}>
              {MODULES.map((mod) => (
                <ModuleCard key={mod.id} mod={mod} />
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4 flex flex-col gap-px" style={{ background: C.border }}>
          <div style={{ background: C.bg }}>
            <RegimeStatisticsPanel />
          </div>
          <div style={{ background: C.bg }}>
            <CalibrationDiagnosticsPanel />
          </div>
        </div>
      </div>
    </div>
  );
}
