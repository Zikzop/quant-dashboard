"use client";

import { C } from "@/lib/colors";
import { Panel, AlertStrip } from "@/components/ui/primitives";

export default function MarketFeed() {
  const alerts: Array<{ text: string; severity: "info" | "warning" | "danger" | "critical" }> = [
    { text: "BTC volatility expansion detected — monitor spread regime", severity: "warning" },
    { text: "Macro liquidity tightening risk — reduce exposure", severity: "danger" },
    { text: "Trend persistence weakening — alpha quality review needed", severity: "info" },
  ];

  return (
    <Panel label="MARKET INTELLIGENCE FEED" accent={C.cyan}>
      <div className="space-y-1">
        {alerts.map((a, i) => (
          <AlertStrip key={i} text={a.text} severity={a.severity} />
        ))}
      </div>
    </Panel>
  );
}
