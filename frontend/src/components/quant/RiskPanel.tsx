"use client";

import { C } from "@/lib/colors";
import { T } from "@/lib/tokens";
import { fmt, fmtPct } from "@/lib/format";
import { Panel, StatRow, Divider, StatusBadge } from "@/components/ui/primitives";
import { useRiskStore } from "@/state/stores/useRiskStore";

export default function RiskPanel({ market }: any) {
  const pf = useRiskStore((s) => s.propFirm);
  const rm = useRiskStore((s) => s.riskMetrics);

  return (
    <Panel label="RISK METRICS" accent={C.danger}>
      <div className="space-y-0.5">
        <StatRow label="VaR 95%" value={market.var_95 != null ? fmt(market.var_95) : fmt(rm.var_95, 0)} accent={C.bearish} />
        <StatRow label="CVaR 95%" value={fmt(rm.cvar_95, 0)} accent={C.bearish} />
        <StatRow label="EXP SHORTFALL" value={market.expected_shortfall ?? "--"} accent={C.bearish} />
        <StatRow label="MAX DRAWDOWN" value={market.max_drawdown ?? "--"} accent={C.critical} />
        <StatRow label="RISK REGIME" value={market.risk_regime ?? "--"} />
      </div>
      <Divider label="PROP FIRM" />
      <div className="flex items-center justify-between mb-1.5">
        <span style={{ fontSize: T.sm, color: C.t2 }}>STATUS</span>
        <StatusBadge
          label={pf.status}
          color={pf.status === "SAFE" ? C.safe : pf.status === "WARNING" ? C.warning : C.critical}
          pulse={pf.status !== "SAFE"}
        />
      </div>
      <StatRow label="DAILY REMAINING" value={`$${fmt(pf.remaining_daily_loss, 0)}`} accent={C.safe} />
      <StatRow label="MAX REMAINING" value={`$${fmt(pf.remaining_max_loss, 0)}`} accent={C.safe} />
    </Panel>
  );
}
