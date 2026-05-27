"use client";

import { C } from "@/lib/colors";
import { Panel } from "@/components/ui/primitives";
import CrossAssetHeatmap from "./CrossAssetHeatmap";

export default function HeatmapPanel({
  market,
}: {
  market: { correlation?: Record<string, unknown> };
}) {
  return (
    <Panel label="CROSS-ASSET CORRELATION" accent={C.amber} noPad>
      <div className="p-3">
        <CrossAssetHeatmap correlation={market?.correlation as any} />
      </div>
    </Panel>
  );
}
