// ─────────────────────────────────────────────────────────────────────────────
// EXECUTION REALISM ENGINE
//
// A signal is only as good as the fill behind it. This engine models the
// microstructure conditions an order would actually face:
//
//   • Trading session (Asia / London / NY / NY-London overlap / off-hours)
//   • Opening-drive detection (first hour of NY / London)
//   • Liquidity quality + estimated half-spread (bps)
//   • Expected slippage for a marketable order (vol- and liquidity-scaled)
//   • Composite execution risk
//   • Volatility-adjusted stop distance (ATR-style, from realized vol)
//
// All session logic is computed in UTC from the latest bar timestamp so it is
// deterministic and SSR-safe (no dependence on the viewer's local clock).
// ─────────────────────────────────────────────────────────────────────────────

import type { ChartBar, MarketPayload } from "@/types/market";
import { getAssetDefinition } from "@/lib/assets/registry";
import type {
  ExecutionState,
  LiquidityQuality,
  SessionName,
} from "@/engines/types";

function latestBarUtcHour(bars: ChartBar[]): number | null {
  if (!bars.length) return null;
  const t = bars[bars.length - 1].time;
  let ms: number;
  if (typeof t === "number") {
    ms = t < 1e12 ? t * 1000 : t; // seconds vs ms
  } else {
    const parsed = Date.parse(t);
    if (Number.isNaN(parsed)) return null;
    ms = parsed;
  }
  return new Date(ms).getUTCHours() + new Date(ms).getUTCMinutes() / 60;
}

// London 07:00–16:00 UTC, NY 12:00–21:00 UTC, overlap 12:00–16:00 UTC.
function classifySession(hour: number | null): { session: SessionName; quality: number } {
  if (hour == null) return { session: "OFF_HOURS", quality: 0.5 };
  const inLondon = hour >= 7 && hour < 16;
  const inNy = hour >= 12 && hour < 21;
  if (inLondon && inNy) return { session: "NY_LONDON_OVERLAP", quality: 1.0 };
  if (inNy) return { session: "NY", quality: 0.85 };
  if (inLondon) return { session: "LONDON", quality: 0.75 };
  if (hour >= 0 && hour < 7) return { session: "ASIA", quality: 0.55 };
  return { session: "OFF_HOURS", quality: 0.4 };
}

function isOpeningDrive(hour: number | null): boolean {
  if (hour == null) return false;
  // First hour of London (07:00–08:00) or NY (12:00–13:00) cash open.
  return (hour >= 7 && hour < 8) || (hour >= 12 && hour < 13.5);
}

function realizedBarVolPct(bars: ChartBar[], lookback = 14): number {
  const slice = bars.slice(-lookback - 1);
  if (slice.length < 2) return 0;
  const trs: number[] = [];
  for (let i = 1; i < slice.length; i++) {
    const h = slice[i].high;
    const l = slice[i].low;
    const pc = slice[i - 1].close;
    const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
    if (slice[i].close > 0) trs.push(tr / slice[i].close);
  }
  if (!trs.length) return 0;
  return (trs.reduce((a, b) => a + b, 0) / trs.length) * 100;
}

export function computeExecutionState(market: MarketPayload): ExecutionState {
  const bars = market.chart_data ?? [];
  const hour = latestBarUtcHour(bars);
  const { session, quality } = classifySession(hour);
  const openingDrive = isOpeningDrive(hour);

  const assetClass = getAssetDefinition(market.asset_id ?? market.symbol ?? "")?.class ?? "crypto";

  // Base half-spread by asset class (bps) — liquid futures/index tighter than crypto.
  const baseSpread: Record<string, number> = {
    equity_index: 0.5,
    macro: 0.6,
    commodity: 1.0,
    crypto: 1.5,
    future: 0.8,
    index: 0.7,
    equity: 1.0,
  };
  const atrPct = realizedBarVolPct(bars);
  const volRegime = (market.vol_regime ?? "").toUpperCase();
  const volMult =
    volRegime.includes("EXPAND") || volRegime.includes("HIGH")
      ? 2.0
      : volRegime.includes("COMPRESS") || volRegime.includes("LOW")
        ? 0.7
        : 1.0;

  // Spread widens off-session and during vol expansion.
  const sessionSpreadMult = 1 + (1 - quality) * 1.5;
  const spreadBps = (baseSpread[assetClass] ?? 1.2) * volMult * sessionSpreadMult;

  // Liquidity quality from session + vol.
  let liquidity: LiquidityQuality;
  if (quality >= 0.85 && volMult <= 1.2) liquidity = "DEEP";
  else if (quality >= 0.7) liquidity = "NORMAL";
  else if (quality >= 0.5) liquidity = "THIN";
  else liquidity = "ILLIQUID";

  // Expected slippage: half-spread + vol/liquidity impact, inflated on the open.
  const liquidityPenalty = { DEEP: 0.2, NORMAL: 0.5, THIN: 1.2, ILLIQUID: 2.5 }[liquidity];
  const expectedSlippageBps =
    spreadBps * 0.5 + atrPct * 8 * liquidityPenalty * (openingDrive ? 1.4 : 1);

  const executionRisk = clamp01(
    0.25 * (1 - quality) +
      0.35 * Math.min(1, expectedSlippageBps / 12) +
      0.25 * (volMult - 0.7) / 1.3 +
      (openingDrive ? 0.15 : 0),
  );

  // Volatility-adjusted stop: ~2.0x ATR (clamped to a sane band).
  const volAdjustedStopPct = Math.max(0.15, Math.min(8, atrPct * 2.0));
  const price = market.price ?? bars[bars.length - 1]?.close ?? 0;
  const volAdjustedStopPrice = price * (volAdjustedStopPct / 100);

  const warnings: string[] = [];
  if (liquidity === "ILLIQUID") warnings.push("ILLIQUID SESSION — WIDE SPREADS, EXECUTION DEGRADED");
  else if (liquidity === "THIN") warnings.push("THIN LIQUIDITY — EXPECT SLIPPAGE ON MARKET ORDERS");
  if (openingDrive) warnings.push("OPENING DRIVE — ELEVATED SLIPPAGE & WHIPSAW RISK");
  if (executionRisk > 0.6) warnings.push("HIGH EXECUTION RISK — PREFER LIMIT ORDERS / REDUCE SIZE");

  return {
    session,
    sessionQuality: quality,
    openingDrive,
    liquidity,
    spreadBps,
    expectedSlippageBps,
    executionRisk,
    volAdjustedStopPct,
    volAdjustedStopPrice,
    warnings,
  };
}

function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}
