"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct } from "@/lib/format";
import { Panel, StatRow, Divider } from "@/components/ui/primitives";

export default function VolatilityPanel({ market }: any) {
  const state = market.market_state;
  const volColor = regimeColor(state?.volatility_regime ?? market.vol_regime);

  return (
    <Panel label="VOLATILITY ANALYTICS" accent={C.volatile}>
      <div className="space-y-0.5">
        <StatRow label="REALIZED VOL" value={`${fmt(market.volatility)}%`} accent={C.volatile} />
        <StatRow label="GARCH VOL" value={market.garch_vol != null ? fmt(market.garch_vol, 4) : "--"} accent={C.volatile} />
        <StatRow label="VOL REGIME" value={market.vol_regime ?? "--"} accent={volColor} />
        <StatRow label="VOL SLOPE" value={market.vol_slope != null ? fmt(market.vol_slope, 4) : "--"} accent={market.vol_slope > 0 ? C.danger : C.safe} />
      </div>
      <Divider label="RISK STATE" />
      <StatRow label="RISK STATE" value={state?.risk_state ?? "--"} />
      <StatRow label="CONFIDENCE" value={state?.confidence != null ? fmtPct(state.confidence) : "--"} accent={(state?.confidence ?? 0) > 0.7 ? C.bullish : C.warning} />
    </Panel>
  );
}
