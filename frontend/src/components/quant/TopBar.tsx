"use client";

import { C, regimeColor, statusColor, pnlColor } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { fmt, fmtPct, fmtUsd } from "@/lib/format";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useRiskStore } from "@/state/stores/useRiskStore";
import { usePortfolioStore } from "@/state/stores/usePortfolioStore";
import type { MarketPayload } from "@/types/market";

type Tier = "primary" | "medium" | "secondary";

// Tier-based sizing drives the scanning hierarchy: PRIMARY states read first
// (asset / regime / signal / risk), MEDIUM second (vol / adx), the rest support.
const TIER: Record<Tier, { label: number; value: number; weight: number }> = {
  primary: { label: T.nano, value: T.md, weight: 700 },
  medium: { label: T.nano, value: T.base, weight: 700 },
  secondary: { label: T.pico, value: T.sm, weight: 600 },
};

function TopMetric({
  label,
  value,
  accent,
  tier = "secondary",
}: {
  label: string;
  value: string;
  accent?: string;
  tier?: Tier;
}) {
  const t = TIER[tier];
  return (
    <div className="flex items-baseline gap-1.5">
      <span style={{ fontSize: t.label, color: C.t3, letterSpacing: TRACK.label }}>{label}</span>
      <span
        style={{
          fontSize: t.value,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: t.weight,
          color: accent ?? C.t1,
          letterSpacing: TRACK.value,
        }}
      >
        {value}
      </span>
    </div>
  );
}

function WsIndicator() {
  const status = useMarketStore((s) => s.wsStatus);
  const latency = useMarketStore((s) => s.wsLatency);
  const color = status === "CONNECTED" ? C.safe : status === "RECONNECTING" ? C.warning : C.danger;

  return (
    <div className="flex items-center gap-1.5">
      <div className="relative" style={{ width: 6, height: 6 }}>
        {status === "RECONNECTING" && (
          <div className="absolute w-1.5 h-1.5 rounded-full animate-ping" style={{ background: color, opacity: 0.5 }} />
        )}
        <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      </div>
      <span style={{ fontSize: T.nano, color, letterSpacing: "0.08em", fontWeight: 600 }}>
        {status === "CONNECTED" ? `${latency}ms` : status}
      </span>
    </div>
  );
}

export default function TopBar({ market }: { market: MarketPayload }) {
  const activeAsset = useTimeframeStore((s) => s.activeAsset);
  const activeTF = useTimeframeStore((s) => s.activeTimeframe);
  const activeRange = useTimeframeStore((s) => s.activeRange);
  const state = market.market_state;
  const pf = useRiskStore((s) => s.propFirm);
  const totalPnl = usePortfolioStore((s) => s.totalPnl);
  const rColor = regimeColor(state?.market_regime);

  return (
    <div
      className="flex items-center justify-between px-4"
      style={{
        background: C.bg,
        borderBottom: `1px solid ${C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
        height: CHROME.topbar,
      }}
    >
      <div className="flex items-center gap-5">
        <span
          style={{
            fontSize: T.md,
            fontWeight: 800,
            color: C.bullish,
            letterSpacing: "0.14em",
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          QT
        </span>
        <div className="h-4 w-px" style={{ background: C.borderMid }} />
        <TopMetric
          label={activeAsset}
          value={market.price != null ? fmtUsd(market.price, 0) : "--"}
          tier="primary"
        />
        <TopMetric label="TF" value={activeTF} tier="secondary" />
        <TopMetric label="RNG" value={activeRange} tier="secondary" />
        <div className="h-4 w-px" style={{ background: C.border }} />
        <TopMetric label="REGIME" value={state?.market_regime ?? "--"} accent={rColor} tier="primary" />
        <TopMetric label="VOL" value={fmtPct(state?.volatility ?? market.volatility)} accent={C.volatile} tier="medium" />
        <TopMetric label="ADX" value={fmt(state?.adx)} accent={rColor} tier="medium" />
        <TopMetric label="SIGNAL" value={market.signal ?? "--"} accent={market.signal === "BUY" ? C.bullish : market.signal === "SELL" ? C.bearish : C.t2} tier="primary" />
      </div>

      <div className="flex items-center gap-5">
        <TopMetric
          label="PnL"
          value={`${totalPnl >= 0 ? "+" : ""}${fmtUsd(totalPnl, 0)}`}
          accent={pnlColor(totalPnl)}
          tier="primary"
        />
        <TopMetric
          label="PROP"
          value={pf.status}
          accent={statusColor(pf.status)}
          tier="primary"
        />
        <div className="h-4 w-px" style={{ background: C.border }} />
        <WsIndicator />
      </div>
    </div>
  );
}
