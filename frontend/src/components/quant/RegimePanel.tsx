"use client";

import { C, regimeColor } from "@/lib/colors";
import { T } from "@/lib/tokens";
import { Panel, StatRow, StatusBadge, Divider } from "@/components/ui/primitives";

export default function RegimePanel({ market }: any) {
  const marketRegime = market.regime ?? market.market_state?.market_regime ?? "--";
  const hmmRegime = market.hmm_regime ?? "--";
  const volRegime = market.vol_regime ?? market.market_state?.volatility_regime ?? "--";

  return (
    <Panel label="REGIME STATE" accent={regimeColor(marketRegime)}>
      <div className="space-y-2">
        <div>
          <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.12em", marginBottom: 4 }}>MARKET REGIME</div>
          <StatusBadge label={marketRegime} color={regimeColor(marketRegime)} pulse />
        </div>
        <Divider />
        <StatRow label="HMM REGIME" value={hmmRegime} accent={regimeColor(hmmRegime)} />
        <StatRow label="VOL REGIME" value={volRegime} accent={regimeColor(volRegime)} />
        <StatRow label="TRANSITION RISK" value={market.market_state?.transition_risk ?? "--"}
          accent={market.market_state?.transition_risk === "ELEVATED" ? C.danger : C.t1} />
        <StatRow label="PERSISTENCE" value={market.market_state?.trend_persistence ?? "--"} />
      </div>
    </Panel>
  );
}
