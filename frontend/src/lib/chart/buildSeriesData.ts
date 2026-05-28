import { C } from "@/lib/colors";
import { finiteNum } from "@/lib/format";
import type { ChartBar } from "@/types/market";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ChartTime = any;

export function chartTime(v: string | number): ChartTime {
  return v;
}

export interface ChartSeriesBundle {
  candles: Array<{ time: ChartTime; open: number; high: number; low: number; close: number }>;
  ema20: Array<{ time: ChartTime; value: number }>;
  ema50: Array<{ time: ChartTime; value: number }>;
  trendOverlay: Array<{ time: ChartTime; value: number }>;
  volOverlay: Array<{ time: ChartTime; value: number }>;
  crisisOverlay: Array<{ time: ChartTime; value: number }>;
  volHist: Array<{ time: ChartTime; value: number; color: string }>;
  transitions: Array<{ time: ChartTime; value: number; color: string }>;
  markers: Array<{
    time: ChartTime;
    position: string;
    color: string;
    shape: string;
    text: string;
    size: number;
  }>;
}

export function buildChartSeries(
  bars: ChartBar[],
  signalsSuppressed: boolean,
): ChartSeriesBundle {
  const t = chartTime;

  const candles = bars.map((b) => ({
    time: t(b.time),
    open: finiteNum(b.open),
    high: finiteNum(b.high),
    low: finiteNum(b.low),
    close: finiteNum(b.close),
  }));
  const ema20 = bars.map((b) => ({ time: t(b.time), value: finiteNum(b.ema20) }));
  const ema50 = bars.map((b) => ({ time: t(b.time), value: finiteNum(b.ema50) }));

  const toOverlay = (subset: ChartBar[]) =>
    subset.map((b) => ({ time: t(b.time), value: b.close }));

  const volHist = bars.map((b) => ({
    time: t(b.time),
    value: finiteNum(b.garch_vol),
    color:
      finiteNum(b.close) > finiteNum(b.open)
        ? "rgba(34,197,94,0.40)"
        : "rgba(239,68,68,0.40)",
  }));

  const transitions = bars.map((b, idx) => {
    const prev = bars[idx - 1];
    const isTransition =
      prev &&
      ((b.hmm_regime && prev.hmm_regime !== b.hmm_regime) ||
        (b.direction && prev.direction !== b.direction));
    return {
      time: t(b.time),
      value: isTransition ? (volHist[idx]?.value ?? 0) * 3 : 0,
      color: "rgba(239,68,68,0.9)",
    };
  });

  const markers: ChartSeriesBundle["markers"] = [];
  if (!signalsSuppressed) {
    bars.forEach((b, idx) => {
      const prev = bars[idx - 1];
      if (!prev) return;
      const dirChanged =
        b.direction && prev.direction && b.direction !== prev.direction;
      const hmmChanged =
        b.hmm_regime && prev.hmm_regime && b.hmm_regime !== prev.hmm_regime;
      if (!dirChanged && !hmmChanged) return;

      const dir = (b.direction ?? "").toUpperCase();
      if (dir.includes("BULL")) {
        markers.push({
          time: t(b.time),
          position: "belowBar",
          color: C.bullish,
          shape: "arrowUp",
          text: "BULL REGIME",
          size: 1,
        });
      } else if (dir.includes("BEAR")) {
        markers.push({
          time: t(b.time),
          position: "aboveBar",
          color: C.bearish,
          shape: "arrowDown",
          text: "BEAR REGIME",
          size: 1,
        });
      } else if (b.hmm_regime === "CRISIS" || hmmChanged) {
        markers.push({
          time: t(b.time),
          position: "aboveBar",
          color: C.volatile,
          shape: "circle",
          text: "REGIME BREAK",
          size: 1,
        });
      }
    });
  }

  return {
    candles,
    ema20,
    ema50,
    trendOverlay: toOverlay(bars.filter((b) => b.hmm_regime === "TRENDING")),
    volOverlay: toOverlay(bars.filter((b) => b.hmm_regime === "MEAN_REVERT")),
    crisisOverlay: toOverlay(bars.filter((b) => b.hmm_regime === "CRISIS")),
    volHist,
    transitions,
    markers,
  };
}
