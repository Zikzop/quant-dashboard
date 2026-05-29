"use client";

import type { DecisionState } from "@/engines/types";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { AssetSelector } from "./AssetSelector";
import { TimeframeSelector } from "./TimeframeSelector";
import { RangeSelector } from "./RangeSelector";
import { ControlLayerProvider } from "./ControlLayerContext";
import { useControlContext } from "./useControlContext";
import { CONTROL, GROUP } from "./controlTokens";

export function MarketControlLayer({
  decision,
}: {
  decision: DecisionState | null;
}) {
  const alignment = useTimeframeStore((s) => s.alignment);
  const context = useControlContext(decision, alignment);

  return (
    <div
      className="market-control-layer shrink-0"
      style={{
        borderBottom: `1px solid ${GROUP.borderMid}`,
        background: GROUP.surface,
        fontFamily: CONTROL.font,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* System context accent stripe */}
      {context.accentStripe && (
        <div
          className="absolute left-0 top-0 bottom-0 pointer-events-none"
          style={{
            width: 2,
            background: context.accentStripe,
            opacity: 0.55,
            boxShadow: `0 0 12px ${context.accentStripe}33`,
          }}
        />
      )}

      {/* Subtle layer tint */}
      {context.layerTint && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: context.layerTint }}
        />
      )}

      <ControlLayerProvider value={context}>
        <div className="relative">
          <AssetSelector />
          <TimeframeSelector />
          <RangeSelector />
        </div>
      </ControlLayerProvider>
    </div>
  );
}
