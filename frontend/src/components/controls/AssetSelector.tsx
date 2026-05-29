"use client";

import { useEffect, useMemo, useState } from "react";

import { C } from "@/lib/colors";
import { T } from "@/lib/tokens";
import { ASSET_DISPLAY_GROUPS, ASSET_IDS } from "@/lib/assets/registry";
import { fetchAssets, type AssetInfo } from "@/lib/api";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { ControlGroup, ControlGroupDivider, ControlMicroLabel } from "./ControlGroup";
import { SegmentedControl } from "./SegmentedControl";
import { CLASS_COLORS } from "./controlTokens";

const FALLBACK: AssetInfo[] = [
  { asset_id: "BTC", provider_symbol: "BTC-USD", asset_class: "crypto", quote_currency: "USD", timezone: "UTC", session: {} },
  { asset_id: "GOLD", provider_symbol: "GC=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "ES", provider_symbol: "ES=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "NQ", provider_symbol: "NQ=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "DXY", provider_symbol: "DX-Y.NYB", asset_class: "index", quote_currency: "USD", timezone: "America/New_York", session: {} },
];

export function AssetSelector() {
  const activeAsset = useTimeframeStore((s) => s.activeAsset);
  const setActiveAsset = useTimeframeStore((s) => s.setActiveAsset);
  const [assets, setAssets] = useState<AssetInfo[]>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    fetchAssets()
      .then((res) => {
        if (!cancelled && res.assets.length) {
          const ordered = ASSET_IDS.map(
            (id) => res.assets.find((a) => a.asset_id === id) ?? FALLBACK.find((f) => f.asset_id === id),
          ).filter(Boolean) as AssetInfo[];
          setAssets(ordered.length ? ordered : res.assets);
        }
      })
      .catch(() => {
        /* keep fallback universe */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const assetMap = useMemo(
    () => new Map(assets.map((a) => [a.asset_id, a])),
    [assets],
  );

  const activeInfo = assetMap.get(activeAsset);
  const activeClassColor = CLASS_COLORS[activeInfo?.asset_class ?? ""] ?? C.cyan;

  const trailing = (
    <>
      <span
        style={{
          fontSize: T.nano,
          color: C.t3,
          letterSpacing: "0.1em",
          fontWeight: 500,
        }}
      >
        {activeInfo?.provider_symbol ?? activeAsset}
      </span>
      <div
        className="rounded-full"
        style={{
          width: 5,
          height: 5,
          background: activeClassColor,
          boxShadow: `0 0 6px ${activeClassColor}55`,
        }}
      />
    </>
  );

  return (
    <ControlGroup label="ASSET" tier="primary" trailing={trailing}>
      {ASSET_DISPLAY_GROUPS.map((group, gi) => {
        const groupAssets = group.ids
          .map((id) => assetMap.get(id))
          .filter(Boolean) as AssetInfo[];

        if (!groupAssets.length) return null;

        return (
          <div key={group.label} className="flex shrink-0 items-stretch">
            {gi > 0 && <ControlGroupDivider />}
            <ControlMicroLabel>{group.label}</ControlMicroLabel>
            {groupAssets.map((a) => {
              const isActive = a.asset_id === activeAsset;
              const cColor = CLASS_COLORS[a.asset_class] ?? C.t3;
              return (
                <SegmentedControl
                  key={a.asset_id}
                  label={a.asset_id}
                  isActive={isActive}
                  onClick={() => setActiveAsset(a.asset_id)}
                  tier="primary"
                  accentColor={cColor}
                  title={`${a.provider_symbol} · ${a.asset_class}`}
                  indicator={
                    <div
                      className="rounded-full transition-all"
                      style={{
                        width: isActive ? 6 : 4,
                        height: isActive ? 6 : 4,
                        background: cColor,
                        boxShadow: isActive ? `0 0 8px ${cColor}88` : "none",
                        opacity: isActive ? 1 : 0.65,
                        transition: "width 80ms ease, height 80ms ease, box-shadow 120ms ease, opacity 80ms ease",
                      }}
                    />
                  }
                />
              );
            })}
          </div>
        );
      })}
    </ControlGroup>
  );
}
