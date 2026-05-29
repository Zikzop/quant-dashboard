"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import type { DecisionState } from "@/engines/types";

type WorkflowStep = {
  id: string;
  label: string;
  verdict: string;
  accent: string;
  sub?: string;
};

function buildSteps(d: DecisionState): WorkflowStep[] {
  const tradeVerdict = d.suppressTrade
    ? "NO TRADE"
    : d.capital.recommendation === "FULL_SIZE"
      ? "TRADE · FULL"
      : d.capital.recommendation === "NO_TRADE"
        ? "NO TRADE"
        : `TRADE · ${d.capital.recommendedRiskR.toFixed(2)}R`;

  const tradeColor = d.suppressTrade || d.capital.recommendation === "NO_TRADE"
    ? C.danger
    : d.capital.recommendedRiskR >= 0.75
      ? C.bullish
      : C.cyan;

  const sizeVerdict =
    d.capital.recommendation === "NO_TRADE"
      ? "FLAT"
      : d.capital.recommendedRiskR < 0.5
        ? "REDUCE"
        : d.capital.recommendedRiskR > 0.75
          ? "INCREASE"
          : "NORMAL";

  return [
    {
      id: "state",
      label: "1 · MARKET STATE",
      verdict: d.structuralRegime.replace(/_/g, " "),
      accent: d.structuralRegime === "CRISIS" ? C.danger : C.cyan,
      sub: d.lifecycle.phaseLabel,
    },
    {
      id: "opportunity",
      label: "2 · OPPORTUNITY",
      verdict: d.entryQuality.replace(/_/g, " "),
      accent: d.entryQuality === "HIGH" ? C.bullish : d.entryQuality === "AVOID" ? C.danger : C.warning,
      sub: `EDGE ${d.expectedEdgePct >= 0 ? "+" : ""}${d.expectedEdgePct.toFixed(2)}%`,
    },
    {
      id: "risk",
      label: "3 · RISK",
      verdict: d.risk.tailRisk.replace(/_/g, " "),
      accent: d.risk.tailRisk === "LOW" ? C.bullish : d.risk.tailRisk === "EXTREME" ? C.danger : C.warning,
      sub: `DD ${d.expectedDrawdownPct.toFixed(2)}%`,
    },
    {
      id: "capital",
      label: "4 · CAPITAL",
      verdict: tradeVerdict,
      accent: tradeColor,
      sub: `${(d.capital.conviction * 100).toFixed(0)}% conviction · ${sizeVerdict}`,
    },
    {
      id: "execution",
      label: "5 · EXECUTION",
      verdict: d.execution.liquidity,
      accent: d.execution.executionRisk > 0.6 ? C.danger : d.execution.executionRisk > 0.4 ? C.warning : C.bullish,
      sub: `${d.execution.expectedSlippageBps.toFixed(1)}bps slippage est`,
    },
  ];
}

export default function DecisionWorkflowStrip({ decision }: { decision: DecisionState }) {
  const steps = buildSteps(decision);

  return (
    <div
      className="grid grid-cols-5 gap-px"
      style={{ background: C.border, borderBottom: `1px solid ${C.border}` }}
    >
      {steps.map((step) => (
        <div
          key={step.id}
          className="px-3 py-2"
          style={{ background: C.surface, minWidth: 0 }}
        >
          <div style={{ fontSize: T.pico, color: C.t3, letterSpacing: TRACK.label, marginBottom: 4 }}>
            {step.label}
          </div>
          <div
            style={{
              fontSize: T.sm,
              fontWeight: 700,
              color: step.accent,
              letterSpacing: "0.02em",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {step.verdict}
          </div>
          {step.sub && (
            <div style={{ fontSize: T.pico, color: C.t2, marginTop: 2, letterSpacing: "0.04em" }}>
              {step.sub}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
