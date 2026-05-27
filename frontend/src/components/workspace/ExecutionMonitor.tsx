"use client";

import { C, pnlColor } from "@/lib/colors";
import { fmt, fmtMs, fmtBps, fmtUsd, fmtTimestamp } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  StatusBadge,
  Divider,
  MiniTable,
  Sparkline,
  AlertStrip,
} from "@/components/ui/primitives";
import { useExecutionStore } from "@/state/stores/useExecutionStore";
import { useMarketStore } from "@/state/stores/useMarketStore";
import type { OrderStatus } from "@/types/market";

function statusColor(s: OrderStatus): string {
  switch (s) {
    case "FILLED": return C.bullish;
    case "PARTIAL": return C.amber;
    case "PENDING": return C.blue;
    case "REJECTED": return C.critical;
    case "CANCELLED": return C.t3;
    default: return C.neutral;
  }
}

function LiveOrdersPanel() {
  const orders = useExecutionStore((s) => s.orders);

  const counts = {
    PENDING: orders.filter((o) => o.status === "PENDING").length,
    FILLED: orders.filter((o) => o.status === "FILLED").length,
    PARTIAL: orders.filter((o) => o.status === "PARTIAL").length,
    REJECTED: orders.filter((o) => o.status === "REJECTED").length,
  };

  return (
    <Panel label="LIVE ORDERS" accent={C.blue} tag={`${orders.length} TOTAL`}>
      <div className="grid grid-cols-4 gap-1 mb-2">
        <StatCell label="PENDING" value={`${counts.PENDING}`} accent={C.blue} />
        <StatCell label="FILLED" value={`${counts.FILLED}`} accent={C.bullish} />
        <StatCell label="PARTIAL" value={`${counts.PARTIAL}`} accent={C.amber} />
        <StatCell label="REJECTED" value={`${counts.REJECTED}`} accent={C.critical} />
      </div>

      <MiniTable
        headers={["TIME", "SYMBOL", "SIDE", "QTY", "FILL", "SLIPPAGE", "STATUS"]}
        rows={orders.map((o) => ({
          highlight: o.status === "REJECTED",
          cells: [
            { value: fmtTimestamp(o.timestamp) },
            { value: o.symbol },
            { value: o.side, accent: o.side === "BUY" ? C.bullish : C.bearish },
            { value: `${o.filled_quantity}/${o.quantity}` },
            { value: o.avg_fill_price > 0 ? fmtUsd(o.avg_fill_price, 1) : "--" },
            { value: fmtBps(o.slippage_bps), accent: o.slippage_bps > 3 ? C.danger : o.slippage_bps > 1 ? C.warning : C.t1 },
            { value: o.status, accent: statusColor(o.status) },
          ],
        }))}
      />
    </Panel>
  );
}

function SlippagePanel() {
  const slip = useExecutionStore((s) => s.slippage);

  return (
    <Panel label="SLIPPAGE ANALYTICS" accent={C.volatile}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="AVG SLIPPAGE" value={fmtBps(slip.avg_slippage_bps)} accent={slip.avg_slippage_bps > 3 ? C.danger : C.t1} large />
        <StatCell label="MAX SLIPPAGE" value={fmtBps(slip.max_slippage_bps)} accent={slip.max_slippage_bps > 5 ? C.danger : C.warning} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="SLIPPAGE σ" value={fmtBps(slip.slippage_stddev)} />
        <StatRow label="POSITIVE SLIP %" value={`${fmt(slip.positive_slippage_pct, 0)}%`} accent={C.bullish} />
      </div>
      <Divider label="RECENT (10)" />
      <div className="flex items-center gap-3">
        <Sparkline data={slip.recent_slippage} width={160} height={24} color={C.volatile} />
        <div style={{ fontSize: 9, color: C.t3 }}>bps</div>
      </div>
      {slip.avg_slippage_bps > 3 && (
        <div className="mt-2">
          <AlertStrip text="ELEVATED SLIPPAGE — CHECK LIQUIDITY CONDITIONS" severity="warning" />
        </div>
      )}
    </Panel>
  );
}

function LatencyPanel() {
  const lat = useExecutionStore((s) => s.latency);
  const wsLat = useMarketStore((s) => s.wsLatency);

  return (
    <Panel label="LATENCY MONITORING" accent={C.cyan}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="WS LATENCY" value={fmtMs(wsLat || lat.ws_latency_ms)} accent={lat.ws_latency_ms > 50 ? C.warning : C.safe} large />
        <StatCell label="EXEC LATENCY" value={fmtMs(lat.execution_latency_ms)} accent={lat.execution_latency_ms > 100 ? C.danger : C.t1} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="AVG RTT" value={fmtMs(lat.avg_round_trip_ms)} />
        <StatRow label="P99 LATENCY" value={fmtMs(lat.p99_latency_ms)} accent={lat.p99_latency_ms > 200 ? C.danger : C.t1} />
        <StatRow label="JITTER" value={fmtMs(lat.jitter_ms)} accent={lat.jitter_ms > 20 ? C.warning : C.t1} />
      </div>
      {lat.p99_latency_ms > 200 && (
        <div className="mt-2">
          <AlertStrip text="HIGH P99 LATENCY — EXECUTION DEGRADATION RISK" severity="danger" />
        </div>
      )}
    </Panel>
  );
}

function BrokerHealthPanel() {
  const bh = useExecutionStore((s) => s.brokerHealth);
  const lastHb = Date.now() - bh.last_heartbeat;
  const stale = lastHb > 30000;

  return (
    <Panel label="BROKER HEALTH" accent={bh.api_status === "CONNECTED" ? C.safe : C.danger}>
      <div className="space-y-1 mb-2">
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 9, color: C.t2 }}>API STATUS</span>
          <StatusBadge
            label={bh.api_status}
            color={bh.api_status === "CONNECTED" ? C.safe : bh.api_status === "DEGRADED" ? C.warning : C.critical}
            pulse={bh.api_status !== "CONNECTED"}
          />
        </div>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 9, color: C.t2 }}>WS STATUS</span>
          <StatusBadge
            label={bh.ws_status}
            color={bh.ws_status === "CONNECTED" ? C.safe : bh.ws_status === "RECONNECTING" ? C.warning : C.critical}
            pulse={bh.ws_status !== "CONNECTED"}
          />
        </div>
      </div>
      <Divider />
      <div className="space-y-0.5">
        <StatRow label="RECONNECTS" value={`${bh.reconnect_count}`} accent={bh.reconnect_count > 0 ? C.warning : C.t1} />
        <StatRow label="LAST HEARTBEAT" value={stale ? "STALE" : `${Math.floor(lastHb / 1000)}s ago`} accent={stale ? C.danger : C.t1} />
        <StatRow label="UPTIME" value={`${fmt(bh.uptime_pct)}%`} accent={bh.uptime_pct > 99.9 ? C.safe : C.warning} />
      </div>
      {(bh.api_status !== "CONNECTED" || bh.ws_status !== "CONNECTED") && (
        <div className="mt-2">
          <AlertStrip text="BROKER CONNECTION DEGRADED — EXECUTION AT RISK" severity="critical" />
        </div>
      )}
    </Panel>
  );
}

export default function ExecutionMonitor() {
  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12" style={{ background: C.bg }}>
          <LiveOrdersPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <SlippagePanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <LatencyPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <BrokerHealthPanel />
        </div>
      </div>
    </div>
  );
}
