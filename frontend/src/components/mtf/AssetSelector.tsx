"use client";

import { useEffect, useState } from "react";

import { C } from "@/lib/colors";
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
  const activeSymbol = useTimeframeStore((s) => s.activeSymbol);
  const setActiveSymbol = useTimeframeStore((s) => s.setActiveSymbol);
  const [assets, setAssets] = useState<AssetInfo[]>(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    fetchAssets()
      .then((res) => {
        if (!cancelled && res.assets.length) setAssets(res.assets);
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
        height: 26,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      <div
        className="flex items-center px-2 gap-1"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.15em" }}>ASSET</span>
      </div>

      {assets.map((a) => {
        const isActive = a.asset_id === activeSymbol;
        const cColor = CLASS_COLORS[a.asset_class] ?? C.t3;
        return (
          <button
            key={a.asset_id}
            onClick={() => setActiveSymbol(a.asset_id)}
            title={`${a.provider_symbol} · ${a.asset_class}`}
            className="relative flex items-center gap-1 px-2.5 h-full transition-colors"
            style={{
              background: isActive ? C.surface2 : "transparent",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive ? `2px solid ${cColor}` : "2px solid transparent",
              color: isActive ? C.t1 : C.t3,
              fontSize: 9,
              fontWeight: isActive ? 700 : 500,
              letterSpacing: "0.06em",
              cursor: "pointer",
            }}
          >
            <div className="w-1 h-1 rounded-full" style={{ background: cColor }} />
            {a.asset_id}
          </button>
        );
      })}

      <div className="flex-1" />
      <div className="flex items-center gap-2 px-3" style={{ borderLeft: `1px solid ${C.border}` }}>
        <span style={{ fontSize: 8, color: C.t3, letterSpacing: "0.1em" }}>
          {assets.find((a) => a.asset_id === activeSymbol)?.provider_symbol ?? activeSymbol}
        </span>
      </div>
    </div>
  );
}
