"use client";

import { useEffect, useState } from "react";

import { C } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { ASSET_IDS } from "@/lib/assets/registry";
import { fetchAssets, type AssetInfo } from "@/lib/api";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

const CLASS_COLORS: Record<string, string> = {
  crypto: C.cyan,
  future: C.purple,
  index: C.blue,
  fx: C.warning,
};

// Sensible default universe shown before /assets resolves (matches the backend
// registry); replaced by the live list once it loads.
const FALLBACK: AssetInfo[] = [
  { asset_id: "BTC", provider_symbol: "BTC-USD", asset_class: "crypto", quote_currency: "USD", timezone: "UTC", session: {} },
  { asset_id: "GOLD", provider_symbol: "GC=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "ES", provider_symbol: "ES=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "NQ", provider_symbol: "NQ=F", asset_class: "future", quote_currency: "USD", timezone: "America/New_York", session: {} },
  { asset_id: "DXY", provider_symbol: "DX-Y.NYB", asset_class: "index", quote_currency: "USD", timezone: "America/New_York", session: {} },
];

export default function AssetSelector() {
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

  return (
    <div
      className="flex items-center"
      style={{
        background: C.surface,
        borderBottom: `1px solid ${C.border}`,
        height: CHROME.selector,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <div
        className="flex items-center px-3 gap-1"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>ASSET</span>
      </div>

      {assets.map((a) => {
        const isActive = a.asset_id === activeAsset;
        const cColor = CLASS_COLORS[a.asset_class] ?? C.t3;
        return (
          <button
            key={a.asset_id}
            onClick={() => setActiveAsset(a.asset_id)}
            title={`${a.provider_symbol} · ${a.asset_class}`}
            className="relative flex items-center gap-1.5 px-3.5 h-full transition-colors"
            style={{
              background: isActive ? C.surface2 : "transparent",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive ? `2px solid ${cColor}` : "2px solid transparent",
              color: isActive ? C.t1 : C.t2,
              fontSize: T.sm,
              fontWeight: isActive ? 700 : 500,
              letterSpacing: "0.06em",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              if (!isActive) e.currentTarget.style.background = C.surface;
            }}
            onMouseLeave={(e) => {
              if (!isActive) e.currentTarget.style.background = "transparent";
            }}
          >
            <div
              className="rounded-full transition-all"
              style={{
                width: isActive ? 6 : 5,
                height: isActive ? 6 : 5,
                background: cColor,
                boxShadow: isActive ? `0 0 6px ${cColor}` : "none",
              }}
            />
            {a.asset_id}
          </button>
        );
      })}

      <div className="flex-1" />
      <div className="flex items-center gap-2 px-3.5" style={{ borderLeft: `1px solid ${C.border}` }}>
        <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.1em" }}>
          {assets.find((a) => a.asset_id === activeAsset)?.provider_symbol ?? activeAsset}
        </span>
      </div>
    </div>
  );
}
