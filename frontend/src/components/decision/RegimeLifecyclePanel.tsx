"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import type { RegimeLifecycleState } from "@/engines/types";

function stabilityColor(s: RegimeLifecycleState["regimeStability"]): string {
  return s === "STABLE" ? C.bullish : s === "FRAGILE" ? C.warning : C.danger;
}

export default function RegimeLifecyclePanel({ lifecycle }: { lifecycle: RegimeLifecycleState }) {
  const phaseColor = lifecycle.regimePhase.includes("EXHAUSTION") || lifecycle.regimePhase.includes("CRISIS")
    ? C.danger
    : lifecycle.regimePhase.includes("EARLY")
      ? C.bullish
      : C.cyan;

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderTop: `2px solid ${regimeColor(lifecycle.currentRegime)}`,
        fontFamily: "'IBM Plex Sans', sans-serif",
      }}
    >
      <div
        className="flex items-center justify-between px-3"
        style={{ height: 28, borderBottom: `1px solid ${C.border}`, background: C.bg }}
      >
        <span style={{ fontSize: T.nano, color: C.t2, letterSpacing: TRACK.label, fontWeight: 700 }}>
          REGIME LIFECYCLE
        </span>
        <span style={{ fontSize: T.pico, color: stabilityColor(lifecycle.regimeStability), fontWeight: 600 }}>
          {lifecycle.regimeStability}
        </span>
      </div>

      <div className="px-3 py-3">
        <div style={{ fontSize: T.lg, fontWeight: 700, color: phaseColor, letterSpacing: "0.02em", marginBottom: 2 }}>
          {lifecycle.phaseLabel}
        </div>
        <div style={{ fontSize: T.micro, color: C.t2, marginBottom: 10 }}>
          {lifecycle.currentRegime.replace(/_/g, " ")}
        </div>

        <div className="grid grid-cols-2 gap-2 mb-2">
          <Metric label="REGIME AGE" value={`${lifecycle.regimeAgeBars}b`} />
          <Metric
            label="REMAINING"
            value={lifecycle.expectedRemainingBars != null ? `${lifecycle.expectedRemainingBars.toFixed(0)}b` : "--"}
          />
        </div>

        <div style={{ fontSize: T.pico, color: C.t3, letterSpacing: TRACK.label, marginBottom: 4 }}>
          LIFECYCLE PROGRESS
        </div>
        <div style={{ height: 6, background: C.border, marginBottom: 4 }}>
          <div
            style={{
              height: "100%",
              width: `${Math.min(100, lifecycle.lifecyclePct * 100)}%`,
              background: phaseColor,
              opacity: 0.8,
            }}
          />
        </div>
        <div style={{ fontSize: T.pico, color: C.t2, textAlign: "right" }}>
          {(lifecycle.lifecyclePct * 100).toFixed(0)}% elapsed
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: T.pico, color: C.t3, letterSpacing: TRACK.label, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: T.md, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: C.t1 }}>
        {value}
      </div>
    </div>
  );
}
