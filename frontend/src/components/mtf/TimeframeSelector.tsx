"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { TIMEFRAMES, TF_LABELS, TF_ROLE, type Timeframe } from "@/types/market";

const ROLE_COLORS: Record<string, string> = {
  EXECUTION: C.cyan,
  TACTICAL: C.blue,
  STRATEGIC: C.purple,
};

export default function TimeframeSelector() {
  const active = useTimeframeStore((s) => s.activeTimeframe);
  const setActive = useTimeframeStore((s) => s.setActiveTimeframe);
  const alignment = useTimeframeStore((s) => s.alignment);
  const regimes = useTimeframeStore((s) => s.regimes);

  const alignColor =
    alignment.state === "ALIGNED" ? C.safe :
    alignment.state === "PARTIAL" ? C.warning : C.danger;

  return (
    <div
      className="flex items-center"
      style={{
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        height: CHROME.selector,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <div
        className="flex items-center px-3 gap-1"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>TF</span>
      </div>

      {TIMEFRAMES.map((tf) => {
        const isActive = active === tf;
        const regime = regimes.find((r) => r.timeframe === tf);
        const roleColor = ROLE_COLORS[TF_ROLE[tf]] ?? C.t3;
        const rColor = regime ? regimeColor(regime.regime) : C.t3;

        return (
          <button
            key={tf}
            onClick={() => setActive(tf)}
            className="relative flex items-center gap-1.5 px-3 h-full transition-colors"
            style={{
              background: isActive ? C.surface2 : "transparent",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive ? `2px solid ${roleColor}` : "2px solid transparent",
              color: isActive ? C.t1 : C.t2,
              fontSize: T.micro,
              fontWeight: isActive ? 700 : 500,
              letterSpacing: "0.06em",
              cursor: "pointer",
            }}
          >
            <div
              className="rounded-full"
              style={{ width: 5, height: 5, background: rColor }}
            />
            {tf}
          </button>
        );
      })}

      <div className="flex-1" />

      <div
        className="flex items-center gap-2 px-3.5"
        style={{ borderLeft: `1px solid ${C.border}` }}
      >
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: alignColor }} />
          <span style={{ fontSize: T.nano, color: alignColor, letterSpacing: "0.1em", fontWeight: 700 }}>
            {alignment.state}
          </span>
        </div>
        <span style={{ fontSize: T.nano, color: C.t3 }}>
          {alignment.aligned_count}/{alignment.total}
        </span>
        {alignment.macro_micro_divergence && (
          <span style={{ fontSize: T.pico, color: C.danger, letterSpacing: "0.06em", fontWeight: 700 }}>
            HTF/LTF DIV
          </span>
        )}
      </div>
    </div>
  );
}
