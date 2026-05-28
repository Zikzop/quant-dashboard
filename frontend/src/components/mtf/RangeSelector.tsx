"use client";

import { C } from "@/lib/colors";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { HISTORICAL_RANGES } from "@/types/market";

export default function RangeSelector() {
  const activeRange = useTimeframeStore((s) => s.activeRange);
  const setActiveRange = useTimeframeStore((s) => s.setActiveRange);
  const loadingTimeframes = useTimeframeStore((s) => s.loadingTimeframes);
  const isLoading = loadingTimeframes.length > 0;

  return (
    <div
      className="flex items-center"
      style={{
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        height: 26,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <div
        className="flex items-center px-2 gap-1"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.15em" }}>RANGE</span>
      </div>

      {HISTORICAL_RANGES.map((range) => {
        const isActive = activeRange === range;
        return (
          <button
            key={range}
            onClick={() => setActiveRange(range)}
            className="relative flex items-center px-2.5 h-full transition-colors"
            style={{
              background: isActive ? C.surface2 : "transparent",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive ? `2px solid ${C.cyan}` : "2px solid transparent",
              color: isActive ? C.t1 : C.t3,
              fontSize: 9,
              fontWeight: isActive ? 700 : 500,
              letterSpacing: "0.06em",
              cursor: "pointer",
            }}
          >
            {range}
          </button>
        );
      })}

      <div className="flex-1" />
      {isLoading && (
        <span
          className="animate-pulse px-3"
          style={{ fontSize: 8, color: C.volatile, letterSpacing: "0.1em" }}
        >
          SYNCING...
        </span>
      )}
    </div>
  );
}
