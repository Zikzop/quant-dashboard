/**
 * Institutional asset registry — single source of truth for the frontend.
 * Mirrors backend/assets/registry.py; API /assets remains authoritative for
 * session metadata, but selectors and labels derive from here.
 *
 * Future multi-asset intelligence (divergence, stress) should reference
 * ASSET_REGISTRY + CROSS_ASSET_GROUPS — not ad-hoc symbol strings.
 */

export type AssetClass = "crypto" | "future" | "index" | "commodity" | "equity_index" | "macro";

export interface AssetDefinition {
  symbol: string;
  type: "crypto" | "future" | "index";
  class: AssetClass;
}

export const ASSET_REGISTRY: Record<string, AssetDefinition> = {
  BTC: { symbol: "BTC-USD", type: "crypto", class: "crypto" },
  GOLD: { symbol: "GC=F", type: "future", class: "commodity" },
  ES: { symbol: "ES=F", type: "future", class: "equity_index" },
  NQ: { symbol: "NQ=F", type: "future", class: "equity_index" },
  DXY: { symbol: "DX-Y.NYB", type: "index", class: "macro" },
};

export const ASSET_IDS = Object.keys(ASSET_REGISTRY) as (keyof typeof ASSET_REGISTRY)[];

/** Display grouping for the asset control bar — subtle class separators, not large headers. */
export const ASSET_DISPLAY_GROUPS = [
  { label: "CRYPTO", ids: ["BTC"] as const },
  { label: "MACRO", ids: ["DXY", "GOLD"] as const },
  { label: "IDX", ids: ["ES", "NQ"] as const },
] as const;

/** Prepared for Phase 4 cross-asset intelligence — not wired yet. */
export const CROSS_ASSET_GROUPS = {
  MACRO_FX_COMMODITY: ["GOLD", "DXY"] as const,
  EQUITY_INDEX_STRESS: ["ES", "NQ"] as const,
  CRYPTO_MACRO: ["BTC", "DXY"] as const,
} as const;

export function getAssetDefinition(assetId: string): AssetDefinition | undefined {
  return ASSET_REGISTRY[assetId.toUpperCase()];
}

export function getProviderSymbol(assetId: string): string {
  return getAssetDefinition(assetId)?.symbol ?? assetId;
}

export function getAssetDisplayLabel(assetId: string): string {
  const def = getAssetDefinition(assetId);
  if (!def) return assetId;
  return def.symbol.replace("-", " / ").replace("=F", "");
}

export function marketMatchesAsset(
  market: { asset_id?: string; symbol?: string } | null,
  activeAsset: string,
): boolean {
  if (!market) return false;
  const id = (market.asset_id ?? "").toUpperCase();
  if (id && id === activeAsset.toUpperCase()) return true;
  const provider = getProviderSymbol(activeAsset);
  return (market.symbol ?? "").toUpperCase() === provider.toUpperCase();
}
