import type { ChartBar } from "@/types/market";

export function timeKey(v: string | number | null | undefined): number {
  if (typeof v === "number") return v;
  return Date.parse(String(v));
}

/** lightweight-charts requires strictly ascending, unique timestamps. */
export function sanitizeChartBars(chartData: ChartBar[]): ChartBar[] {
  const sorted = [...chartData]
    .filter((b) => b.time != null && Number.isFinite(timeKey(b.time)))
    .sort((a, b) => timeKey(a.time) - timeKey(b.time));

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
