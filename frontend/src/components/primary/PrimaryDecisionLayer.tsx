"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import type {
  DecisionState,
  DirectionBias,
  EntryQualityRating,
  StabilityLevel,
  UncertaintyLevel,
} from "@/engines/types";

// ─────────────────────────────────────────────────────────────────────────────
// LEVEL 1 — PRIMARY DECISION LAYER
//
// The dominant surface. Seven institutional reads, legible in under 2 seconds:
//   Regime · Direction · Alignment · Entry Quality · Risk State · Confidence ·
//   Regime Stability — plus the quantified verdict that replaces "STRONG BUY":
//   Expected Edge / Confidence / Regime Stability.
// ─────────────────────────────────────────────────────────────────────────────

function directionColor(d: DirectionBias): string {
  return d === "LONG" ? C.bullish : d === "SHORT" ? C.bearish : C.neutral;
}

function stabilityColor(s: StabilityLevel): string {
  return s === "STABLE" ? C.bullish : s === "FRAGILE" ? C.warning : C.danger;
}

function qualityColor(q: EntryQualityRating): string {
  return q === "HIGH" ? C.bullish : q === "ACCEPTABLE" ? C.cyan : q === "LOW_EDGE" ? C.warning : C.danger;
}

function uncertaintyColor(u: UncertaintyLevel): string {
  return u === "LOW" ? C.bullish : u === "MODERATE" ? C.cyan : u === "HIGH" ? C.warning : C.danger;
}

function stabilityWord(s: StabilityLevel): string {
  return s === "STABLE" ? "HIGH" : s === "FRAGILE" ? "MODERATE" : "LOW";
}

// A primary "read" tile — label small/dim, value large/bright.
function Read({
  label,
  value,
  accent,
  sub,
}: {
  label: string;
  value: string;
  accent?: string;
  sub?: string;
}) {
  return (
    <div className="flex flex-col justify-center" style={{ minWidth: 0 }}>
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label, marginBottom: 3 }}>
        {label}
      </span>
      <span
        style={{
          fontSize: T.lg,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 700,
          color: accent ?? C.t1,
          letterSpacing: TRACK.value,
          lineHeight: 1.05,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {value}
      </span>
      {sub && (
        <span style={{ fontSize: T.pico, color: C.t3, letterSpacing: "0.06em", marginTop: 2 }}>
          {sub}
        </span>
      )}
    </div>
  );
}

export default function PrimaryDecisionLayer({ decision }: { decision: DecisionState }) {
  const dirColor = directionColor(decision.direction);
  const rColor = regimeColor(decision.structuralRegime);
  const edge = decision.expectedEdgePct;
  const edgeColor = edge > 0.02 ? C.bullish : edge < -0.02 ? C.bearish : C.neutral;
  const confPct = Math.round(decision.confidence * 100);
  const alignColor =
    decision.alignmentState === "ALIGNED" ? C.bullish : decision.alignmentState === "PARTIAL" ? C.warning : C.danger;

  return (
    <div
      style={{
        background: `linear-gradient(180deg, ${C.surface} 0%, ${C.bg} 100%)`,
        borderTop: `1px solid ${C.border}`,
        borderBottom: `1px solid ${C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      }}
    >
      {/* Headline warnings — only when present. */}
      {decision.headline.length > 0 && (
        <div
          className="flex items-center gap-4 overflow-x-auto px-4"
          style={{ background: "rgba(220,38,38,0.07)", borderBottom: `1px solid ${C.border}`, height: 22 }}
        >
          {decision.headline.map((h) => (
            <div key={h} className="flex items-center gap-1.5" style={{ flexShrink: 0 }}>
              <span className="soft-pulse" style={{ width: 5, height: 5, borderRadius: 9, background: C.danger, display: "inline-block" }} />
              <span style={{ fontSize: T.nano, color: C.danger, letterSpacing: "0.1em", fontWeight: 700 }}>{h}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-stretch">
        {/* ── DECISION VERDICT — dominant left block ───────────────────────── */}
        <div
          className="flex flex-col justify-center px-5 py-3"
          style={{ borderRight: `1px solid ${C.border}`, minWidth: 280, flexShrink: 0 }}
        >
          <div className="flex items-center gap-2 mb-1">
            <span style={{ width: 8, height: 8, borderRadius: 9, background: dirColor }} className="soft-pulse" />
            <span style={{ fontSize: T.xxl, fontWeight: 800, color: dirColor, letterSpacing: TRACK.display, lineHeight: 1 }}>
              {decision.directionLabel}
            </span>
          </div>
          <div className="flex items-baseline gap-2" style={{ marginTop: 2 }}>
            <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>EXPECTED EDGE</span>
            <span
              style={{
                fontSize: T.xl,
                fontFamily: "'IBM Plex Mono', monospace",
                fontWeight: 700,
                color: edgeColor,
                letterSpacing: TRACK.value,
              }}
            >
              {edge >= 0 ? "+" : ""}
              {edge.toFixed(2)}%
            </span>
          </div>
          <div className="flex items-center gap-3" style={{ marginTop: 4 }}>
            <span style={{ fontSize: T.nano, color: C.t3 }}>
              CONF <span style={{ color: confPct > 60 ? C.bullish : confPct > 40 ? C.warning : C.danger, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700 }}>{confPct}%</span>
            </span>
            <span style={{ fontSize: T.nano, color: C.t3 }}>
              STABILITY <span style={{ color: stabilityColor(decision.regimeStability), fontWeight: 700 }}>{stabilityWord(decision.regimeStability)}</span>
            </span>
            <span style={{ fontSize: T.nano, color: C.t3 }}>
              EXP DD <span style={{ color: C.bearish, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700 }}>{decision.expectedDrawdownPct.toFixed(2)}%</span>
            </span>
          </div>
          {decision.suppressTrade && (
            <div
              className="mt-2 inline-flex items-center self-start"
              style={{ background: "rgba(239,68,68,0.1)", border: `1px solid ${C.danger}`, padding: "2px 8px" }}
            >
              <span style={{ fontSize: T.pico, color: C.danger, letterSpacing: "0.12em", fontWeight: 700 }}>
                ⚠ SIGNAL SUPPRESSED — NO EXECUTABLE EDGE
              </span>
            </div>
          )}
        </div>

        {/* ── SEVEN PRIMARY READS — even grid ──────────────────────────────── */}
        <div className="flex-1 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-x-5 gap-y-3 px-5 py-3">
          <Read
            label="STRUCTURAL REGIME"
            value={decision.structuralRegime.replace(/_/g, " ")}
            accent={rColor}
            sub={`MICRO · ${decision.microRegime.replace(/_/g, " ")}`}
          />
          <Read
            label="EXECUTION BIAS"
            value={decision.executionBias.replace(/_/g, " ")}
            accent={decision.executionBias === "NO_TRADE" ? C.danger : dirColor}
          />
          <Read
            label="MTF ALIGNMENT"
            value={decision.alignmentState}
            accent={alignColor}
            sub={`${Math.round(decision.alignmentRatio * 100)}% AGREEMENT`}
          />
          <Read
            label="ENTRY QUALITY"
            value={decision.entryQuality.replace(/_/g, " ")}
            accent={qualityColor(decision.entryQuality)}
            sub={`SCORE ${(decision.entryScore * 100).toFixed(0)}`}
          />
          <Read
            label="RISK STATE"
            value={decision.riskState.replace(/_/g, " ")}
            accent={decision.risk.tailRisk === "LOW" ? C.t1 : C.warning}
            sub={`TAIL · ${decision.risk.tailRisk.replace(/_/g, " ")}`}
          />
          <Read
            label="UNCERTAINTY"
            value={decision.uncertaintyLevel}
            accent={uncertaintyColor(decision.uncertaintyLevel)}
            sub={`σ ${(decision.uncertainty.score * 100).toFixed(0)}`}
          />
        </div>
      </div>
    </div>
  );
}
