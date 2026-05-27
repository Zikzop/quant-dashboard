"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct } from "@/lib/format";
import { Panel, Divider, StatusBadge, AlertStrip } from "@/components/ui/primitives";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { TF_ROLE, type TimeframeRegime, type Timeframe } from "@/types/market";

function dirColor(dir: string): string {
  const d = dir.toUpperCase();
  if (d.includes("BULL")) return C.bullish;
  if (d.includes("BEAR")) return C.bearish;
  return C.neutral;
}

function TFRow({ r }: { r: TimeframeRegime }) {
  const rColor = regimeColor(r.regime);
  const dColor = dirColor(r.direction);
  const role = TF_ROLE[r.timeframe];
  const roleColor = role === "STRATEGIC" ? C.purple : role === "TACTICAL" ? C.blue : C.cyan;

  return (
    <div
      className="flex items-center py-[3px]"
      style={{ borderBottom: `1px solid ${C.border}` }}
    >
      <div className="flex items-center gap-1" style={{ width: 44, flexShrink: 0 }}>
        <div className="w-1 h-3" style={{ background: roleColor }} />
        <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: C.t1 }}>
          {r.timeframe}
        </span>
      </div>

      <div style={{ width: 70, flexShrink: 0 }}>
        <span style={{ fontSize: 8, fontWeight: 700, color: rColor, letterSpacing: "0.04em" }}>
          {r.regime.replace(/_/g, " ")}
        </span>
      </div>

      <div style={{ width: 48, flexShrink: 0 }}>
        <span style={{ fontSize: 8, color: dColor, fontWeight: 600 }}>
          {r.direction}
        </span>
      </div>

      <div style={{ width: 42, flexShrink: 0 }}>
        <span style={{ fontSize: 8, fontFamily: "'IBM Plex Mono', monospace", color: rColor }}>
          {r.trend_strength}
        </span>
      </div>

      <div style={{ width: 30, flexShrink: 0, textAlign: "right" }}>
        <span style={{ fontSize: 8, fontFamily: "'IBM Plex Mono', monospace", color: C.t2 }}>
          {fmt(r.adx, 0)}
        </span>
      </div>

      <div className="flex-1 px-1">
        <div className="flex gap-px h-[4px]">
          <div style={{ width: `${r.trend_probability * 100}%`, background: C.bullish, minWidth: 1 }} />
          <div style={{ width: `${r.mean_revert_probability * 100}%`, background: C.cyan, minWidth: 1 }} />
          <div style={{ width: `${r.crisis_probability * 100}%`, background: C.danger, minWidth: 1 }} />
        </div>
      </div>

      <div style={{ width: 28, textAlign: "right", flexShrink: 0 }}>
        <span style={{
          fontSize: 8, fontFamily: "'IBM Plex Mono', monospace",
          color: r.confidence > 0.7 ? C.bullish : r.confidence > 0.4 ? C.warning : C.danger,
        }}>
          {(r.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

export default function MTFRegimeMatrix() {
  const regimes = useTimeframeStore((s) => s.regimes);
  const alignment = useTimeframeStore((s) => s.alignment);

  const alignColor =
    alignment.state === "ALIGNED" ? C.safe :
    alignment.state === "PARTIAL" ? C.warning : C.danger;

  const reversed = [...regimes].reverse();

  return (
    <Panel
      label="MULTI-TIMEFRAME REGIME MATRIX"
      accent={alignColor}
      tag={`${alignment.state} ${alignment.aligned_count}/${alignment.total}`}
    >
      {/* Header */}
      <div className="flex items-center py-[2px] mb-1" style={{ borderBottom: `1px solid ${C.borderMid}` }}>
        <span style={{ width: 44, fontSize: 7, color: C.t3, letterSpacing: "0.1em" }}>TF</span>
        <span style={{ width: 70, fontSize: 7, color: C.t3, letterSpacing: "0.1em" }}>REGIME</span>
        <span style={{ width: 48, fontSize: 7, color: C.t3, letterSpacing: "0.1em" }}>DIR</span>
        <span style={{ width: 42, fontSize: 7, color: C.t3, letterSpacing: "0.1em" }}>STR</span>
        <span style={{ width: 30, fontSize: 7, color: C.t3, letterSpacing: "0.1em", textAlign: "right" }}>ADX</span>
        <span className="flex-1 px-1" style={{ fontSize: 7, color: C.t3, letterSpacing: "0.1em" }}>PROB</span>
        <span style={{ width: 28, fontSize: 7, color: C.t3, letterSpacing: "0.1em", textAlign: "right" }}>CONF</span>
      </div>

      {reversed.map((r) => (
        <TFRow key={r.timeframe} r={r} />
      ))}

      <Divider label="ALIGNMENT" />

      <div className="flex items-center gap-2 mb-1">
        <StatusBadge label={alignment.state} color={alignColor} pulse={alignment.state === "CONFLICT"} />
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 8, color: C.t3 }}>HTF</span>
          <span style={{ fontSize: 8, fontWeight: 700, color: dirColor(alignment.htf_bias) }}>{alignment.htf_bias}</span>
          <span style={{ fontSize: 8, color: C.t3 }}>LTF</span>
          <span style={{ fontSize: 8, fontWeight: 700, color: dirColor(alignment.ltf_bias) }}>{alignment.ltf_bias}</span>
        </div>
      </div>

      {alignment.details.map((d, i) => (
        <div key={i} style={{ fontSize: 8, color: alignment.state === "ALIGNED" ? C.safe : C.warning, lineHeight: 1.5, letterSpacing: "0.03em" }}>
          {d}
        </div>
      ))}

      {alignment.htf_conflict_penalty > 0.2 && (
        <div className="mt-1">
          <AlertStrip
            text={`HTF CONFLICT PENALTY: -${(alignment.htf_conflict_penalty * 100).toFixed(0)}% ENTRY QUALITY`}
            severity={alignment.htf_conflict_penalty > 0.3 ? "danger" : "warning"}
          />
        </div>
      )}

      <Divider label="LEGEND" />
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <div className="w-2 h-1" style={{ background: C.purple }} />
          <span style={{ fontSize: 7, color: C.t3 }}>STRATEGIC</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-1" style={{ background: C.blue }} />
          <span style={{ fontSize: 7, color: C.t3 }}>TACTICAL</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-1" style={{ background: C.cyan }} />
          <span style={{ fontSize: 7, color: C.t3 }}>EXECUTION</span>
        </div>
      </div>
    </Panel>
  );
}
