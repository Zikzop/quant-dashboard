"use client";

import { C } from "@/lib/colors";
import { probFraction } from "@/lib/format";
import { Panel, ProgressBar, Divider } from "@/components/ui/primitives";

export default function ProbabilityPanel({ market }: any) {
  const bull = probFraction(market.bull_probability);
  const bear = 1 - bull;
  const trend = probFraction(market.trend_probability);
  const meanRev = probFraction(market.mean_revert_probability);
  const crisis = probFraction(market.crisis_probability);
  const volExpand = market.vol_regime?.toUpperCase().includes("EXPAND") ? 0.65 : 0.25;

  return (
    <Panel label="PROBABILISTIC ENGINE" accent={C.bullish}>
      <div className="space-y-1.5">
        <ProgressBar label="BULL" value={bull} color={C.bullish} />
        <ProgressBar label="BEAR" value={bear} color={C.bearish} />
      </div>
      <Divider label="HMM STATE" />
      <div className="space-y-1.5">
        <ProgressBar label="TREND CONT" value={trend} color={C.bullish} />
        <ProgressBar label="MEAN REV" value={meanRev} color={C.cyan} />
        <ProgressBar label="CRISIS" value={crisis} color={C.critical} />
      </div>
      <Divider label="VOLATILITY" />
      <div className="space-y-1.5">
        <ProgressBar label="VOL EXPAND" value={volExpand} color={C.volatile} />
      </div>
    </Panel>
  );
}
