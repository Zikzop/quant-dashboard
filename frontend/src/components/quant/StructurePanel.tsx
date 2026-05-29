"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct } from "@/lib/format";
import { Panel, StatRow, Divider } from "@/components/ui/primitives";

export default function StructurePanel({ market }: any) {
  return (
    <Panel label="STRUCTURE ANALYTICS" accent={C.bullish}>
      <div className="space-y-0.5">
        <StatRow label="TREND" value={market.trend ?? "--"} accent={regimeColor(market.trend)} />
        <StatRow label="MOMENTUM" value={market.momentum ?? "--"} />
        <StatRow label="SIGNAL SCORE" value={fmt(market.signal_score)} accent={market.signal_score > 0.7 ? C.bullish : C.t1} />
        <StatRow label="CONFIDENCE" value={fmt(market.confidence)} accent={(market.confidence ?? 0) > 0.7 ? C.bullish : C.warning} />
      </div>
      <Divider label="DIRECTIONAL" />
      <StatRow label="DIRECTION" value={market.market_state?.direction ?? "--"} accent={
        market.market_state?.direction?.toUpperCase().includes("BULL") ? C.bullish :
        market.market_state?.direction?.toUpperCase().includes("BEAR") ? C.bearish : C.neutral
      } />
      <StatRow label="STRENGTH" value={market.market_state?.trend_strength ?? "--"} accent={regimeColor(market.market_state?.trend_strength)} />
    </Panel>
  );
}
