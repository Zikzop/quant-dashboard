import type { ChartBar } from "@/types/market";

const DAILY_RE = /^\d{4}-\d{2}-\d{2}$/;
// Anything past this (in seconds) is almost certainly a millisecond epoch that
// slipped through; lightweight-charts expects UNIX *seconds* for intraday data.
const MS_THRESHOLD = 1e12;

/**
 * Normalize a single bar's time into a value lightweight-charts accepts:
 *   - intraday  -> UNIX timestamp in **seconds** (integer)
 *   - daily/HTF -> "YYYY-MM-DD" business-day string
 * Returns null when the time cannot be made valid (caller drops the bar).
 */
export function normalizeBarTime(v: string | number | null | undefined): string | number | null {
  if (v == null) return null;

  if (typeof v === "number") {
    if (!Number.isFinite(v) || v <= 0) return null;
    // Coerce millisecond epochs down to seconds so candles land on-screen
    // instead of being placed thousands of years in the future.
    const secs = v > MS_THRESHOLD ? Math.floor(v / 1000) : Math.floor(v);
    return secs;
  }

  const s = String(v).trim();
  if (DAILY_RE.test(s)) return s;

  // Full ISO datetime (e.g. "2024-01-01T00:00:00Z") is NOT a valid
  // lightweight-charts string time — fold it to seconds or a daily key.
  const parsed = Date.parse(s);
  if (Number.isNaN(parsed)) return null;
  // Date-only ISO without time component -> keep as business-day string.
  if (s.length === 10) return s;
  return Math.floor(parsed / 1000);
}

export function timeKey(v: string | number | null | undefined): number {
  if (typeof v === "number") return v > MS_THRESHOLD ? v / 1000 : v;
  return Date.parse(String(v));
}

function validOhlc(b: ChartBar): boolean {
  return (
    Number.isFinite(b.open) &&
    Number.isFinite(b.high) &&
    Number.isFinite(b.low) &&
    Number.isFinite(b.close)
  );
}

/**
 * lightweight-charts requires strictly ascending, unique timestamps of a single
 * (intraday OR daily) type. This:
 *   1. normalizes/validates each bar's time,
 *   2. drops bars with invalid time or invalid OHLC,
 *   3. sorts ascending and collapses duplicate timestamps (keep latest),
 *   4. enforces a single time type (no mixing numbers and strings).
 */
export function sanitizeChartBars(chartData: ChartBar[]): ChartBar[] {
  if (!Array.isArray(chartData) || chartData.length === 0) return [];

  const normalized: ChartBar[] = [];
  for (const b of chartData) {
    const time = normalizeBarTime(b.time);
    if (time == null) continue;
    if (!validOhlc(b)) continue;
    normalized.push({ ...b, time });
  }

  if (normalized.length === 0) return [];

  // Enforce a single time type — pick the majority and discard the rest so
  // lightweight-charts never receives a mixed (string + number) series.
  const numericCount = normalized.filter((b) => typeof b.time === "number").length;
  const wantNumber = numericCount >= normalized.length - numericCount;
  const typed = normalized.filter((b) => (typeof b.time === "number") === wantNumber);

  const sorted = typed.sort((a, b) => timeKey(a.time) - timeKey(b.time));

  const out: ChartBar[] = [];
  for (const b of sorted) {
    const last = out[out.length - 1];
    if (last && timeKey(last.time) === timeKey(b.time)) {
      out[out.length - 1] = b;
    } else {
      out.push(b);
    }
  }
  return out;
}
