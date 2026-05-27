"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct, probFraction } from "@/lib/format";
import type { MarketPayload } from "@/types/market";

function Chip({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-baseline gap-1">
      <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.1em" }}>{label}</span>
      <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, color: accent ?? C.t1 }}>
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
      className="flex items-center gap-6 px-3 py-0.5 overflow-x-auto"
      style={{
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        height: 22,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <Chip label="REGIME" value={state.market_regime} accent={rColor} />
      <Chip label="STRENGTH" value={state.trend_strength ?? "--"} accent={rColor} />
      <Chip label="DIR" value={state.direction ?? "--"} accent={dColor} />
      <Chip label="ADX" value={fmt(state.adx)} accent={rColor} />
      <Chip label="+DI" value={fmt(state.plus_di)} accent={C.bullish} />
      <Chip label="−DI" value={fmt(state.minus_di)} accent={C.bearish} />
      <div className="h-2.5 w-px" style={{ background: C.border }} />
      <Chip label="TREND" value={`${(probFraction(market.trend_probability) * 100).toFixed(0)}%`} accent={C.bullish} />
      <Chip label="CRISIS" value={`${(probFraction(market.crisis_probability) * 100).toFixed(0)}%`} accent={C.critical} />
      <Chip label="VOL" value={state.volatility_regime ?? "--"} accent={regimeColor(state.volatility_regime)} />
      <Chip label="RISK" value={state.risk_state ?? "--"} />
    </div>
  );
}
