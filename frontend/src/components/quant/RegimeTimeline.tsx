"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK, PANEL } from "@/lib/tokens";

export default function RegimeTimeline({ market }: any) {
  const currentHmm = market.hmm_regime ?? "";

  const regimes = [
    { label: "TREND", key: "TREND" },
    { label: "MEAN REVERT", key: "MEAN_REVERT" },
    { label: "VOLATILE", key: "VOLATILE" },
    { label: "CRISIS", key: "CRISIS" },
    { label: "RECOVERY", key: "RECOVERY" },
  ];

  return (
    <div
      style={{
        background: C.bg,
        border: `1px solid ${C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      }}
    >
      <div
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: C.surface,
          padding: `${PANEL.headerPadY}px ${PANEL.headerPadX}px`,
        }}
      >
        <span style={{ fontSize: T.micro, color: C.t2, letterSpacing: TRACK.label, fontWeight: 700 }}>REGIME TIMELINE</span>
      </div>
      <div className="flex">
        {regimes.map((r) => {
          const isActive = currentHmm.toUpperCase().includes(r.key);
          const col = regimeColor(r.key);
          return (
            <div
              key={r.key}
              className="flex-1 py-2.5 text-center"
              style={{
                borderRight: `1px solid ${C.border}`,
                background: isActive ? `${col}15` : "transparent",
                borderBottom: isActive ? `2px solid ${col}` : "2px solid transparent",
              }}
            >
              <span
                style={{
                  fontSize: T.micro,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? col : C.t3,
                  letterSpacing: "0.08em",
                }}
              >
                {r.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
