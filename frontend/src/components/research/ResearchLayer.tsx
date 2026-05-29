"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import { fmt } from "@/lib/format";
import { MiniTable } from "@/components/ui/primitives";
import { useDisclosureStore } from "@/state/stores/useDisclosureStore";
import type { MarketPayload } from "@/types/market";
import type { DecisionState } from "@/engines/types";

// ─────────────────────────────────────────────────────────────────────────────
// LEVEL 3 — RESEARCH / DIAGNOSTICS
//
// Hidden by default. Raw model scores, factor decomposition, internal engine
// scores, calibration diagnostics and debug metrics for research validation.
// ─────────────────────────────────────────────────────────────────────────────

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "10px 12px" }}>
      <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label, fontWeight: 700, marginBottom: 8 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function emaSpread(market: MarketPayload): number {
  const bars = market.chart_data ?? [];
  const last = bars.length ? bars[bars.length - 1] : undefined;
  if (!last) return 0;
  return (last.ema20 ?? 0) - (last.ema50 ?? 0);
}

function KV({ k, v, accent }: { k: string; v: string; accent?: string }) {
  return (
    <div className="flex items-baseline justify-between py-[2px]">
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.04em" }}>{k}</span>
      <span style={{ fontSize: T.sm, fontFamily: "'IBM Plex Mono', monospace", color: accent ?? C.t1, fontWeight: 600 }}>{v}</span>
    </div>
  );
}

export default function ResearchLayer({
  market,
  decision,
}: {
  market: MarketPayload;
  decision: DecisionState;
}) {
  const visible = useDisclosureStore((s) => s.researchVisible);
  const toggle = useDisclosureStore((s) => s.toggleResearch);
  const p = decision.probability;
  const st = market.market_state;

  return (
    <div className="flex flex-col" style={{ background: C.bg, borderTop: `1px solid ${C.border}` }}>
      <button
        onClick={toggle}
        className="flex items-center justify-between px-3"
        style={{ height: 26, background: C.surface, cursor: "pointer", borderBottom: visible ? `1px solid ${C.border}` : "none" }}
      >
        <div className="flex items-center gap-2">
          <span style={{ fontSize: T.micro, color: visible ? C.t1 : C.t3, transform: visible ? "rotate(90deg)" : "none", display: "inline-block", width: 8 }}>▸</span>
          <span style={{ fontSize: T.nano, color: visible ? C.t1 : C.t3, letterSpacing: TRACK.label, fontWeight: 700 }}>
            RESEARCH · DIAGNOSTICS · LEVEL 3
          </span>
        </div>
        <span style={{ fontSize: T.pico, color: C.t4, letterSpacing: "0.1em" }}>
          {visible ? "HIDE" : "SHOW RAW MODEL INTERNALS"}
        </span>
      </button>

      {visible && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-px p-px" style={{ background: C.border }}>
          <Block title="RAW MODEL SCORES (UNCALIBRATED)">
            <KV k="bull_probability" v={fmt(p.bull.raw, 3)} accent={C.bullish} />
            <KV k="trend_probability" v={fmt(p.trend.raw, 3)} />
            <KV k="mean_revert_prob" v={fmt(p.meanRevert.raw, 3)} accent={C.cyan} />
            <KV k="crisis_probability" v={fmt(p.crisis.raw, 3)} accent={C.critical} />
            <KV k="signal_score" v={fmt(market.signal_score, 3)} />
            <KV k="confidence(raw)" v={fmt(market.confidence, 3)} />
            <KV k="momentum" v={typeof market.momentum === "number" ? fmt(market.momentum, 4) : String(market.momentum ?? "--")} />
          </Block>

          <Block title="CALIBRATION DIAGNOSTICS">
            <KV k="method" v={p.diagnostics.method} accent={C.cyan} />
            <KV k="sample_size" v={`${p.diagnostics.sampleSize}`} accent={p.diagnostics.sampleSize > 40 ? C.bullish : C.warning} />
            <KV k="horizon_bars" v={`${p.diagnostics.horizonBars}`} />
            <KV k="platt_A" v={fmt(p.diagnostics.plattA, 3)} />
            <KV k="platt_B" v={fmt(p.diagnostics.plattB, 3)} />
            <KV k="brier_raw" v={p.diagnostics.brierRaw != null ? fmt(p.diagnostics.brierRaw, 4) : "--"} />
            <KV k="brier_calibrated" v={p.diagnostics.brierCalibrated != null ? fmt(p.diagnostics.brierCalibrated, 4) : "--"} accent={p.diagnostics.brierCalibrated != null && p.diagnostics.brierRaw != null && p.diagnostics.brierCalibrated < p.diagnostics.brierRaw ? C.bullish : C.warning} />
          </Block>

          <Block title="FACTOR DECOMPOSITION">
            <KV k="adx" v={fmt(st?.adx, 2)} />
            <KV k="plus_di" v={fmt(st?.plus_di, 2)} accent={C.bullish} />
            <KV k="minus_di" v={fmt(st?.minus_di, 2)} accent={C.bearish} />
            <KV k="garch_vol" v={fmt(market.garch_vol, 5)} accent={C.volatile} />
            <KV k="vol_slope" v={fmt(market.vol_slope, 5)} accent={(market.vol_slope ?? 0) > 0 ? C.danger : C.safe} />
            <KV k="ema20−ema50" v={fmt(emaSpread(market), 2)} />
          </Block>

          <Block title="INTERNAL ENGINE SCORES">
            <KV k="entry_score" v={fmt(decision.entryScore, 3)} accent={C.bullish} />
            <KV k="uncertainty_score" v={fmt(decision.uncertainty.score, 3)} accent={C.warning} />
            <KV k="prob_dispersion" v={fmt(p.dispersion, 3)} />
            <KV k="regime_instability" v={fmt(decision.transition.instability, 3)} accent={C.purple} />
            <KV k="regime_coherence" v={fmt(decision.regime.coherence, 3)} />
            <KV k="exec_risk" v={fmt(decision.execution.executionRisk, 3)} accent={C.blue} />
            <KV k="risk.n_returns" v={`${decision.risk.n}`} />
          </Block>

          <div className="md:col-span-2 xl:col-span-4">
            <Block title="RELIABILITY CURVE (CALIBRATED PREDICTED vs OBSERVED FREQUENCY)">
              {p.diagnostics.reliability.length > 0 ? (
                <MiniTable
                  headers={["BIN", "PREDICTED", "OBSERVED", "N", "GAP"]}
                  rows={p.diagnostics.reliability.map((b, i) => {
                    const gap = b.observed - b.predicted;
                    return {
                      cells: [
                        { value: `${i + 1}` },
                        { value: fmt(b.predicted, 3) },
                        { value: fmt(b.observed, 3) },
                        { value: `${b.n}` },
                        { value: `${gap >= 0 ? "+" : ""}${fmt(gap, 3)}`, accent: Math.abs(gap) > 0.12 ? C.warning : C.bullish },
                      ],
                    };
                  })}
                />
              ) : (
                <span style={{ fontSize: T.sm, color: C.t3 }}>
                  Insufficient samples to fit a reliability curve (need ≥24 labeled bars).
                </span>
              )}
            </Block>
          </div>
        </div>
      )}
    </div>
  );
}
