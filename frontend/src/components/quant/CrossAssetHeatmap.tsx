"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";

interface CorrelationPayload {
  assets?: string[];
  matrix_labels?: string[];
  matrix_values?: (number | null)[][];
  zscore_matrix_values?: number[][];
  beta_vs_btc?: Record<string, number>;
  covariance_instability?: {
    score?: number;
    regime?: string;
    frobenius_delta?: number;
  };
  regime_correlation_shift?: {
    current_regime?: string;
    shift_magnitude?: number;
    sensitivity?: string;
    largest_shifts?: Array<{
      pair: string;
      delta: number;
      long_correlation?: number;
      short_correlation?: number;
    }>;
  };
  heatmap_cells?: Array<{
    asset: string;
    daily_return_pct: number;
    beta_vs_btc: number;
    correlation_zscore_vs_btc: number;
  }>;
}

function cellColor(value: number | null, mode: "corr" | "zscore"): string {
  if (value == null || Number.isNaN(value)) return "rgb(39, 39, 44)";

  if (mode === "zscore") {
    if (value >= 1.5) return "rgba(34, 197, 94, 0.85)";
    if (value >= 0.5) return "rgba(34, 197, 94, 0.45)";
    if (value <= -1.5) return "rgba(239, 68, 68, 0.85)";
    if (value <= -0.5) return "rgba(239, 68, 68, 0.45)";
    return "rgba(107, 114, 128, 0.35)";
  }

  if (value >= 0.6) return "rgba(34, 197, 94, 0.75)";
  if (value >= 0.25) return "rgba(34, 197, 94, 0.4)";
  if (value <= -0.6) return "rgba(239, 68, 68, 0.75)";
  if (value <= -0.25) return "rgba(239, 68, 68, 0.4)";
  return "rgba(107, 114, 128, 0.35)";
}

export default function CrossAssetHeatmap({
  correlation,
}: {
  correlation?: CorrelationPayload;
}) {
  if (!correlation?.matrix_labels?.length) {
    return (
      <p style={{ fontSize: T.sm, color: C.t3, letterSpacing: "0.04em" }}>
        Correlation engine data unavailable.
      </p>
    );
  }

  const summaryCard = (label: string, value: string, accent: string, sub?: string) => (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        padding: "7px 9px",
      }}
    >
      <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>{label}</span>
      <p style={{ fontSize: T.md, fontWeight: 700, color: accent, marginTop: 3, letterSpacing: TRACK.value }}>
        {value}
        {sub && <span style={{ fontSize: T.nano, color: C.t3, marginLeft: 5, fontWeight: 500 }}>{sub}</span>}
      </p>
    </div>
  );

  const labels = correlation.matrix_labels;
  const matrix = correlation.matrix_values ?? [];
  const zMatrix = correlation.zscore_matrix_values ?? [];
  const instability = correlation.covariance_instability;
  const shift = correlation.regime_correlation_shift;
  const cells = correlation.heatmap_cells ?? [];

  return (
    <div className="space-y-4" style={{ fontFamily: "'IBM Plex Sans', system-ui, sans-serif" }}>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-2">
        {summaryCard("COV INSTABILITY", instability?.regime ?? "--", C.volatile, `(${instability?.score?.toFixed(3) ?? "--"})`)}
        {summaryCard("REGIME SHIFT", shift?.sensitivity ?? "--", C.cyan, `(${shift?.shift_magnitude?.toFixed(3) ?? "--"})`)}
        {summaryCard("HMM REGIME", shift?.current_regime ?? "--", C.amber)}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-center">
          <thead>
            <tr>
              <th style={{ padding: 6 }} />
              {labels.map((label) => (
                <th
                  key={label}
                  style={{ padding: 6, fontSize: T.nano, color: C.t3, fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.08em" }}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((rowLabel, rowIdx) => (
              <tr key={rowLabel}>
                <td style={{ padding: 6, fontSize: T.nano, color: C.t2, fontFamily: "'IBM Plex Mono', monospace", textAlign: "left", letterSpacing: "0.06em" }}>
                  {rowLabel}
                </td>
                {labels.map((_, colIdx) => {
                  const corr = matrix[rowIdx]?.[colIdx] ?? null;
                  const z = zMatrix[rowIdx]?.[colIdx] ?? 0;
                  return (
                    <td key={`${rowLabel}-${colIdx}`} style={{ padding: 2 }}>
                      <div
                        style={{
                          background: cellColor(z, "zscore"),
                          border: `1px solid ${C.border}`,
                          padding: "6px 4px",
                        }}
                        title={`ρ=${corr ?? "--"} | z=${z.toFixed(2)}`}
                      >
                        <span style={{ fontSize: T.micro, fontFamily: "'IBM Plex Mono', monospace", color: C.t1, fontWeight: 600 }}>
                          {corr != null ? corr.toFixed(2) : "--"}
                        </span>
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-2">
        {cells.map((cell) => {
          const positive = cell.daily_return_pct >= 0;
          return (
            <div
              key={cell.asset}
              style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "9px 11px" }}
            >
              <p style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>{cell.asset}</p>
              <p
                style={{
                  fontSize: T.lg,
                  fontWeight: 700,
                  marginTop: 3,
                  fontFamily: "'IBM Plex Mono', monospace",
                  color: positive ? C.bullish : C.bearish,
                  letterSpacing: TRACK.display,
                }}
              >
                {positive ? "+" : ""}
                {cell.daily_return_pct.toFixed(2)}%
              </p>
              <p style={{ fontSize: T.nano, color: C.t3, marginTop: 6, fontFamily: "'IBM Plex Mono', monospace" }}>
                β BTC {cell.beta_vs_btc.toFixed(2)}
              </p>
              <p style={{ fontSize: T.nano, color: C.cyan, fontFamily: "'IBM Plex Mono', monospace" }}>
                ρz BTC {cell.correlation_zscore_vs_btc.toFixed(2)}
              </p>
            </div>
          );
        })}
      </div>

      {shift?.largest_shifts?.length ? (
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "11px 13px" }}>
          <p style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label, marginBottom: 10 }}>
            REGIME-SENSITIVE CORRELATION SHIFTS
          </p>
          <div className="space-y-1.5">
            {shift.largest_shifts.map((item) => (
              <div
                key={item.pair}
                className="flex justify-between"
                style={{ fontSize: T.sm, fontFamily: "'IBM Plex Mono', monospace" }}
              >
                <span style={{ color: C.t2 }}>{item.pair}</span>
                <span style={{ color: item.delta >= 0 ? C.bullish : C.bearish, fontWeight: 600 }}>
                  {item.delta >= 0 ? "+" : ""}
                  {item.delta.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
