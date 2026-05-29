"use client";

import { C, regimeColor } from "@/lib/colors";
import { T } from "@/lib/tokens";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { TIMEFRAMES, TF_ROLE, type Timeframe } from "@/types/market";
import { ControlGroup } from "./ControlGroup";
import { SegmentedControl } from "./SegmentedControl";
import { useControlLayerContext } from "./ControlLayerContext";
import { TF_ROLE_COLORS } from "./controlTokens";

export function TimeframeSelector() {
  const active = useTimeframeStore((s) => s.activeTimeframe);
  const setActive = useTimeframeStore((s) => s.setActiveTimeframe);
  const alignment = useTimeframeStore((s) => s.alignment);
  const regimes = useTimeframeStore((s) => s.regimes);
  const { contextLabel, contextColor } = useControlLayerContext();

  const alignColor =
    alignment.state === "ALIGNED" ? C.safe :
    alignment.state === "PARTIAL" ? C.warning : C.danger;

  const trailing = (
    <>
      {contextLabel && (
        <span
          style={{
            fontSize: T.pico,
            color: contextColor ?? C.t3,
            letterSpacing: "0.12em",
            fontWeight: 700,
            paddingRight: 6,
            borderRight: `1px solid ${C.border}`,
            marginRight: 2,
          }}
        >
          {contextLabel}
        </span>
      )}
      <div className="flex items-center gap-1.5">
        <div
          className="rounded-full soft-pulse"
          style={{
            width: 6,
            height: 6,
            background: alignColor,
            boxShadow: `0 0 6px ${alignColor}44`,
          }}
        />
        <span
          style={{
            fontSize: T.nano,
            color: alignColor,
            letterSpacing: "0.1em",
            fontWeight: 700,
          }}
        >
          {alignment.state}
        </span>
      </div>
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.06em" }}>
        {alignment.aligned_count}/{alignment.total}
      </span>
      {alignment.macro_micro_divergence && (
        <span
          style={{
            fontSize: T.pico,
            color: C.danger,
            letterSpacing: "0.08em",
            fontWeight: 700,
            padding: "1px 5px",
            border: `1px solid ${C.danger}33`,
            background: "rgba(239,68,68,0.06)",
          }}
        >
          HTF/LTF DIV
        </span>
      )}
    </>
  );

  return (
    <ControlGroup label="TF" tier="secondary" trailing={trailing}>
      {TIMEFRAMES.map((tf) => {
        const isActive = active === tf;
        const regime = regimes.find((r) => r.timeframe === tf);
        const roleColor = TF_ROLE_COLORS[TF_ROLE[tf as Timeframe]] ?? C.t3;
        const rColor = regime ? regimeColor(regime.regime) : C.t4;

        return (
          <SegmentedControl
            key={tf}
            label={tf}
            isActive={isActive}
            onClick={() => setActive(tf)}
            tier="secondary"
            accentColor={roleColor}
            title={`${TF_ROLE[tf as Timeframe]} · ${regime?.regime ?? "—"}`}
            indicator={
              <div
                className="rounded-full"
                style={{
                  width: 4,
                  height: 4,
                  background: rColor,
                  opacity: isActive ? 1 : 0.7,
                  boxShadow: isActive ? `0 0 4px ${rColor}55` : "none",
                }}
              />
            }
          />
        );
      })}
    </ControlGroup>
  );
}
