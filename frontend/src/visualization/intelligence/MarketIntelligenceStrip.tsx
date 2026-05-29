"use client";

import { C } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { fmt } from "@/lib/format";
import type { MarketPayload } from "@/types/market";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

function Chip({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.labelTight }}>{label}</span>
      <span
        style={{
          fontSize: T.sm,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 600,
          color: accent ?? C.t1,
          letterSpacing: TRACK.value,
        }}
      >
        {value}
      </span>
    </div>
  );
}

/** Context strip — session, asset, timeframe. Regime/probability live in decision layer. */
export default function MarketIntelligenceStrip({ market }: { market: MarketPayload }) {
  const activeAsset = useTimeframeStore((s) => s.activeAsset);
  const activeTF = useTimeframeStore((s) => s.activeTimeframe);
  const activeRange = useTimeframeStore((s) => s.activeRange);

  if (!market) return null;

  const signalColor =
    market.signal?.includes("BUY") ? C.bullish
      : market.signal?.includes("SELL") || market.signal?.includes("AVOID") ? C.danger
        : C.t2;

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
      <Chip label="ASSET" value={activeAsset} accent={C.cyan} />
      <Chip label="TF" value={activeTF} />
      <Chip label="RANGE" value={activeRange} />
      <div className="h-3 w-px" style={{ background: C.borderMid }} />
      <Chip label="PRICE" value={market.price != null ? fmt(market.price, 0) : "--"} accent={C.t1} />
      <Chip label="SIGNAL" value={market.signal ?? "--"} accent={signalColor} />
      <Chip label="VOL" value={market.volatility != null ? `${fmt(market.volatility, 1)}%` : "--"} accent={C.volatile} />
      <div className="h-3 w-px" style={{ background: C.borderMid }} />
      <Chip label="RISK STATE" value={market.market_state?.risk_state ?? "--"} accent={C.t1} />
    </div>
  );
}
