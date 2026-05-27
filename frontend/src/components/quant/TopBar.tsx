"use client";

import { C, regimeColor, statusColor, pnlColor } from "@/lib/colors";
import { fmt, fmtPct, fmtUsd } from "@/lib/format";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useRiskStore } from "@/state/stores/useRiskStore";
import { usePortfolioStore } from "@/state/stores/usePortfolioStore";
import type { MarketPayload } from "@/types/market";

function TopMetric({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.12em" }}>{label}</span>
      <span
        style={{
          fontSize: 11,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 700,
          color: accent ?? C.t1,
          letterSpacing: "0.02em",
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
      <span style={{ fontSize: 8, color, letterSpacing: "0.08em", fontWeight: 600 }}>
        {status === "CONNECTED" ? `${latency}ms` : status}
      </span>
    </div>
  );
}

export default function TopBar({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const pf = useRiskStore((s) => s.propFirm);
  const totalPnl = usePortfolioStore((s) => s.totalPnl);
  const rColor = regimeColor(state?.market_regime);

  return (
    <div
      className="flex items-center justify-between px-3 py-1"
      style={{
        background: C.bg,
        borderBottom: `1px solid ${C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
        height: 32,
      }}
    >
      <div className="flex items-center gap-4">
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            color: C.bullish,
            letterSpacing: "0.12em",
            fontFamily: "'IBM Plex Mono', monospace",
          }}
        >
          QT
        </span>
        <div className="h-3 w-px" style={{ background: C.border }} />
        <TopMetric label="BTC" value={market.price != null ? fmtUsd(market.price, 0) : "--"} />
        <TopMetric label="REGIME" value={state?.market_regime ?? "--"} accent={rColor} />
        <TopMetric label="VOL" value={fmtPct(state?.volatility ?? market.volatility)} accent={C.volatile} />
        <TopMetric label="ADX" value={fmt(state?.adx)} accent={rColor} />
        <TopMetric label="SIGNAL" value={market.signal ?? "--"} accent={market.signal === "BUY" ? C.bullish : market.signal === "SELL" ? C.bearish : C.t2} />
      </div>

      <div className="flex items-center gap-4">
        <TopMetric
          label="PnL"
          value={`${totalPnl >= 0 ? "+" : ""}${fmtUsd(totalPnl, 0)}`}
          accent={pnlColor(totalPnl)}
        />
        <TopMetric
          label="PROP"
          value={pf.status}
          accent={statusColor(pf.status)}
        />
        <div className="h-3 w-px" style={{ background: C.border }} />
        <WsIndicator />
      </div>
    </div>
  );
}
