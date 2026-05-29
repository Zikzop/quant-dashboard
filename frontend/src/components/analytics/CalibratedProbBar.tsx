"use client";

import { C } from "@/lib/colors";
import { T } from "@/lib/tokens";
import type { CalibratedProbability } from "@/engines/types";

// Horizontal probability bar that renders the calibrated point estimate plus
// the confidence-interval band and a ghost marker for the raw (uncalibrated)
// value — making the calibration shrinkage visually explicit.
export function CalibratedProbBar({
  label,
  prob,
  color,
}: {
  label: string;
  prob: CalibratedProbability;
  color: string;
}) {
  const pct = prob.calibrated * 100;
  const lo = prob.interval.lower * 100;
  const hi = prob.interval.upper * 100;
  const rawPct = prob.raw * 100;

  return (
    <div className="flex items-center gap-2">
      <span style={{ fontSize: T.micro, color: C.t2, width: 78, flexShrink: 0, letterSpacing: "0.04em" }}>
        {label}
      </span>
      <div className="flex-1 relative h-[8px]" style={{ background: C.border }}>
        {/* Confidence-interval band */}
        <div
          className="absolute top-0 h-full"
          style={{ left: `${lo}%`, width: `${Math.max(0.5, hi - lo)}%`, background: `${color}33` }}
        />
        {/* Calibrated fill */}
        <div className="absolute top-0 h-full" style={{ width: `${pct}%`, background: color, opacity: 0.85 }} />
        {/* Calibrated point marker */}
        <div className="absolute top-[-1px]" style={{ left: `calc(${pct}% - 1px)`, width: 2, height: 10, background: C.t1 }} />
        {/* Raw (uncalibrated) ghost marker */}
        <div
          className="absolute top-[-1px]"
          style={{ left: `calc(${rawPct}% - 0.5px)`, width: 1, height: 10, background: C.t3 }}
          title={`raw ${rawPct.toFixed(0)}%`}
        />
      </div>
      <span
        style={{
          fontSize: T.sm,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 700,
          color: C.t1,
          width: 64,
          textAlign: "right",
          flexShrink: 0,
        }}
      >
        {pct.toFixed(0)}%
        <span style={{ fontSize: T.pico, color: C.t3, fontWeight: 500 }}>
          {" "}±{((hi - lo) / 2).toFixed(0)}
        </span>
      </span>
    </div>
  );
}
