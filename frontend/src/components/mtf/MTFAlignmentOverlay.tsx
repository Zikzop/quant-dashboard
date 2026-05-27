"use client";

import { C, regimeColor } from "@/lib/colors";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { TF_ROLE } from "@/types/market";

export default function MTFAlignmentOverlay() {
  const regimes = useTimeframeStore((s) => s.regimes);
  const alignment = useTimeframeStore((s) => s.alignment);

  const alignColor =
    alignment.state === "ALIGNED" ? C.safe :
    alignment.state === "PARTIAL" ? C.warning : C.danger;

  const strategicTFs = regimes.filter((r) => TF_ROLE[r.timeframe] === "STRATEGIC");
  const executionTFs = regimes.filter((r) => TF_ROLE[r.timeframe] === "EXECUTION");

  if (regimes.length === 0) return null;

  return (
    <div
      className="absolute top-[180px] left-4 z-40 w-[180px]"
      style={{
        background: "rgba(8,8,9,0.94)",
        border: `1px solid ${C.borderMid}`,
        borderTop: `2px solid ${alignColor}`,
        padding: "8px 10px",
        fontFamily: "'IBM Plex Sans', sans-serif",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>MTF ALIGNMENT</span>
        <div className="flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: alignColor }} />
          <span style={{ fontSize: 8, color: alignColor, fontWeight: 700 }}>{alignment.state}</span>
        </div>
      </div>

      <div className="space-y-[2px]">
        {[...regimes].reverse().map((r) => {
          const rColor = regimeColor(r.regime);
          const dColor = r.direction.toUpperCase().includes("BULL") ? C.bullish :
            r.direction.toUpperCase().includes("BEAR") ? C.bearish : C.neutral;
          return (
            <div key={r.timeframe} className="flex items-center gap-1">
              <span style={{
                fontSize: 8, fontFamily: "'IBM Plex Mono', monospace",
                fontWeight: 700, color: C.t2, width: 22,
              }}>
                {r.timeframe}
              </span>
              <span style={{ fontSize: 7, color: dColor, width: 8, textAlign: "center" }}>
                {r.direction.toUpperCase().includes("BULL") ? "▲" : r.direction.toUpperCase().includes("BEAR") ? "▼" : "─"}
              </span>
              <span style={{
                fontSize: 7, color: rColor, fontWeight: 600,
                letterSpacing: "0.03em", flex: 1,
              }}>
                {r.regime.replace(/_/g, " ")}
              </span>
              <span style={{ fontSize: 7, fontFamily: "'IBM Plex Mono', monospace", color: C.t3 }}>
                {r.trend_strength}
              </span>
            </div>
          );
        })}
      </div>

      {alignment.macro_micro_divergence && (
        <div className="mt-1 px-1 py-0.5" style={{ background: "rgba(239,68,68,0.06)", borderLeft: `2px solid ${C.danger}` }}>
          <span style={{ fontSize: 7, color: C.danger, letterSpacing: "0.04em" }}>
            MACRO/MICRO DIVERGENCE
          </span>
        </div>
      )}

      {alignment.htf_conflict_penalty > 0 && (
        <div className="mt-1">
          <span style={{ fontSize: 7, color: C.warning, letterSpacing: "0.04em" }}>
            ENTRY PENALTY: -{(alignment.htf_conflict_penalty * 100).toFixed(0)}%
          </span>
        </div>
      )}
    </div>
  );
}
