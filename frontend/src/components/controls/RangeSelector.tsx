"use client";

import { C } from "@/lib/colors";
import { T } from "@/lib/tokens";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { HISTORICAL_RANGES } from "@/types/market";
import { ControlGroup } from "./ControlGroup";
import { SegmentedControl } from "./SegmentedControl";

export function RangeSelector() {
  const activeRange = useTimeframeStore((s) => s.activeRange);
  const setActiveRange = useTimeframeStore((s) => s.setActiveRange);
  const loadingTimeframes = useTimeframeStore((s) => s.loadingTimeframes);
  const isLoading = loadingTimeframes.length > 0;

  const trailing = isLoading ? (
    <span
      className="animate-pulse"
      style={{
        fontSize: T.nano,
        color: C.volatile,
        letterSpacing: "0.1em",
        fontWeight: 600,
      }}
    >
      SYNCING…
    </span>
  ) : (
    <span style={{ fontSize: T.pico, color: C.t4, letterSpacing: "0.12em" }}>
      HIST
    </span>
  );

  return (
    <ControlGroup label="RANGE" tier="tertiary" isLast trailing={trailing}>
      {HISTORICAL_RANGES.map((range) => {
        const isActive = activeRange === range;
        return (
          <SegmentedControl
            key={range}
            label={range}
            isActive={isActive}
            onClick={() => setActiveRange(range)}
            tier="tertiary"
            accentColor={C.cyan}
            title={`Historical window: ${range}`}
          />
        );
      })}
    </ControlGroup>
  );
}
