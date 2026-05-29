"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import type { CapitalAllocationState, RiskSizeRecommendation } from "@/engines/types";

const SIZE_LABELS: Record<RiskSizeRecommendation, string> = {
  NO_TRADE: "NO TRADE",
  QUARTER_R: "0.25R",
  HALF_R: "0.50R",
  THREE_QUARTER_R: "0.75R",
  FULL_SIZE: "FULL SIZE",
};

function sizeColor(rec: RiskSizeRecommendation): string {
  switch (rec) {
    case "NO_TRADE": return C.danger;
    case "QUARTER_R": return C.warning;
    case "HALF_R": return C.cyan;
    case "THREE_QUARTER_R": return C.bullish;
    case "FULL_SIZE": return C.bullish;
  }
}

export default function CapitalDeploymentPanel({ capital }: { capital: CapitalAllocationState }) {
  const accent = sizeColor(capital.recommendation);

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        borderTop: `2px solid ${accent}`,
        fontFamily: "'IBM Plex Sans', sans-serif",
      }}
    >
      <div
        className="flex items-center justify-between px-3"
        style={{ height: 28, borderBottom: `1px solid ${C.border}`, background: C.bg }}
      >
        <span style={{ fontSize: T.nano, color: C.t2, letterSpacing: TRACK.label, fontWeight: 700 }}>
          CAPITAL DEPLOYMENT
        </span>
        <span style={{ fontSize: T.pico, color: C.t3, letterSpacing: "0.08em" }}>RISK-FIRST</span>
      </div>

      <div className="px-3 py-3">
        <div className="flex items-baseline gap-3 mb-3">
          <span
            style={{
              fontSize: T.xxl,
              fontWeight: 800,
              color: accent,
              letterSpacing: TRACK.display,
              lineHeight: 1,
            }}
          >
            {SIZE_LABELS[capital.recommendation]}
          </span>
          {capital.recommendation !== "NO_TRADE" && (
            <span style={{ fontSize: T.sm, color: C.t2, fontFamily: "'IBM Plex Mono', monospace" }}>
              {capital.recommendedRiskR.toFixed(2)}R
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2 mb-2">
          <Metric label="EXPOSURE MULT" value={capital.exposureMultiplier.toFixed(2)} accent={C.t1} />
          <Metric label="CONVICTION" value={`${(capital.conviction * 100).toFixed(0)}%`} accent={capital.conviction > 0.6 ? C.bullish : C.warning} />
          <Metric label="SIZE" value={`${capital.recommendedSizePct.toFixed(0)}%`} accent={accent} />
          <Metric label="RISK BUDGET" value={`${capital.riskBudgetUsagePct.toFixed(0)}%`} accent={capital.riskBudgetUsagePct > 75 ? C.danger : C.t1} />
        </div>

        <div style={{ height: 4, background: C.border, marginBottom: 8 }}>
          <div
            style={{
              height: "100%",
              width: `${Math.min(100, capital.riskBudgetUsagePct)}%`,
              background: accent,
              opacity: 0.85,
            }}
          />
        </div>

        <div className="space-y-1">
          {capital.rationale.slice(0, 3).map((r) => (
            <div key={r} style={{ fontSize: T.pico, color: C.t2, letterSpacing: "0.04em", lineHeight: 1.4 }}>
              · {r}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div style={{ fontSize: T.pico, color: C.t3, letterSpacing: TRACK.label, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: T.md, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: accent ?? C.t1 }}>
        {value}
      </div>
    </div>
  );
}
