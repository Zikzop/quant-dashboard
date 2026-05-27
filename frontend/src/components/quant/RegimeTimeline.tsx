"use client";

import { C, regimeColor } from "@/lib/colors";

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
        className="px-3 py-1"
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: C.surface,
        }}
      >
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.2em" }}>REGIME TIMELINE</span>
      </div>
      <div className="flex">
        {regimes.map((r) => {
          const isActive = currentHmm.toUpperCase().includes(r.key);
          const col = regimeColor(r.key);
          return (
            <div
              key={r.key}
              className="flex-1 py-2 text-center"
              style={{
                borderRight: `1px solid ${C.border}`,
                background: isActive ? `${col}15` : "transparent",
                borderBottom: isActive ? `2px solid ${col}` : "2px solid transparent",
              }}
            >
              <span
                style={{
                  fontSize: 9,
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
