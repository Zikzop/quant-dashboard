"use client";

import { C, regimeColor } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { fmt, fmtPct, probFraction } from "@/lib/format";
import type { MarketPayload } from "@/types/market";

function Chip({
  label,
  value,
  accent,
  strong,
}: {
  label: string;
  value: string;
  accent?: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.labelTight }}>{label}</span>
      <span
        style={{
          fontSize: strong ? T.base : T.sm,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: strong ? 700 : 600,
          color: accent ?? C.t1,
          letterSpacing: TRACK.value,
        }}
      >
        {value}
      </span>
    </div>
  );
}

export default function MarketIntelligenceStrip({ market }: { market: MarketPayload }) {
  const state = market?.market_state;
  if (!state) return null;

  const rColor = regimeColor(state.market_regime);
  const dColor = state.direction?.toUpperCase().includes("BULL") ? C.bullish : state.direction?.toUpperCase().includes("BEAR") ? C.bearish : C.neutral;

  return (
    <div
      className="flex items-center gap-6 px-4 overflow-x-auto"
      style={{
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        height: CHROME.strip,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <Chip label="REGIME" value={state.market_regime} accent={rColor} strong />
      <Chip label="STRENGTH" value={state.trend_strength ?? "--"} accent={rColor} />
      <Chip label="DIR" value={state.direction ?? "--"} accent={dColor} />
      <Chip label="ADX" value={fmt(state.adx)} accent={rColor} />
      <Chip label="+DI" value={fmt(state.plus_di)} accent={C.bullish} />
      <Chip label="−DI" value={fmt(state.minus_di)} accent={C.bearish} />
      <div className="h-3 w-px" style={{ background: C.borderMid }} />
      <Chip label="TREND" value={`${(probFraction(market.trend_probability) * 100).toFixed(0)}%`} accent={C.bullish} />
      <Chip label="CRISIS" value={`${(probFraction(market.crisis_probability) * 100).toFixed(0)}%`} accent={C.critical} />
      <Chip label="VOL" value={state.volatility_regime ?? "--"} accent={regimeColor(state.volatility_regime)} />
      <Chip label="RISK" value={state.risk_state ?? "--"} accent={C.t1} strong />
    </div>
  );
}
