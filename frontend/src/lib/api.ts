// ─────────────────────────────────────────────────────────────────────────────
// API CLIENT — single seam between the frontend and the research backend.
//
// * Base URL is environment-driven (NEXT_PUBLIC_API_BASE_URL) so the same build
//   targets local / staging / prod without code changes.
// * Every response is validated at runtime with zod against a schema that
//   mirrors the backend's Pydantic contract. If the backend drifts, we get a
//   loud console warning with the exact path — the frontend half of the
//   "prevent schema drift" guarantee — while still rendering (availability).
// ─────────────────────────────────────────────────────────────────────────────

import { z } from "zod";
import type { MarketPayload } from "@/types/market";

export const API_BASE_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

// ── zod schemas (mirror backend/schemas/market.py) ──────────────────────────

const MarketStateSchema = z
  .object({
    market_regime: z.string(),
    volatility_regime: z.string(),
    trend_persistence: z.string(),
    transition_risk: z.string(),
    confidence: z.number(),
    adx: z.number().nullable().optional(),
    volatility: z.number(),
    risk_state: z.string(),
    trend_strength: z.string().optional(),
    direction: z.string().optional(),
    plus_di: z.number().nullable().optional(),
    minus_di: z.number().nullable().optional(),
  })
  .passthrough();

const ChartBarSchema = z
  .object({
    time: z.union([z.number(), z.string()]),
    open: z.number(),
    high: z.number(),
    low: z.number(),
    close: z.number(),
    ema20: z.number(),
    ema50: z.number(),
  })
  .passthrough();

const RegimeTransitionSchema = z
  .object({
    states: z.array(z.string()),
    matrix: z.record(z.string(), z.record(z.string(), z.number())),
    persistence: z.record(z.string(), z.number()),
    instability_score: z.number(),
    is_unstable: z.boolean(),
    current_state: z.string().nullable().optional(),
  })
  .passthrough();

export const MarketPayloadSchema = z
  .object({
    symbol: z.string(),
    asset_id: z.string().optional(),
    timeframe: z.string(),
    feature_version: z.string().optional(),
    price: z.number(),
    trend: z.string(),
    market_state: MarketStateSchema,
    volatility: z.number(),
    regime: z.string(),
    signal: z.string(),
    garch_vol: z.number(),
    vol_regime: z.string(),
    hmm_regime: z.string(),
    chart_data: z.array(ChartBarSchema),
    regime_transition: RegimeTransitionSchema.optional(),
    correlation: z.unknown().nullable().optional(),
  })
  .passthrough();

export const AssetSchema = z.object({
  asset_id: z.string(),
  provider_symbol: z.string(),
  asset_class: z.string(),
  quote_currency: z.string(),
  timezone: z.string(),
  session: z.record(z.string(), z.unknown()),
});

export const AssetsResponseSchema = z.object({
  assets: z.array(AssetSchema),
  timeframes: z.array(z.string()),
});

export type AssetInfo = z.infer<typeof AssetSchema>;

// ── fetchers ────────────────────────────────────────────────────────────────

function validate<T>(schema: z.ZodType<T>, data: unknown, context: string): void {
  const result = schema.safeParse(data);
  if (!result.success) {
    // Non-fatal: surface drift in dev tools without blocking the UI.
    console.warn(
      `[api] schema drift at ${context}:`,
      result.error.issues.slice(0, 8),
    );
  }
}

export async function fetchMarketTimeframe(
  tf: string,
  symbol: string,
): Promise<MarketPayload> {
  const res = await fetch(
    `${API_BASE_URL}/market/timeframe/${tf}?symbol=${encodeURIComponent(symbol)}`,
  );
  if (!res.ok) throw new Error(`Market API returned ${res.status} for ${tf}`);
  const data = await res.json();
  validate(MarketPayloadSchema, data, `market/${tf}`);
  return data as MarketPayload;
}

export async function fetchAssets(): Promise<z.infer<typeof AssetsResponseSchema>> {
  const res = await fetch(`${API_BASE_URL}/assets`);
  if (!res.ok) throw new Error(`Assets API returned ${res.status}`);
  const data = await res.json();
  validate(AssetsResponseSchema, data, "assets");
  return data as z.infer<typeof AssetsResponseSchema>;
}
