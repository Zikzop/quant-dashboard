"use client";

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
      <p className="text-zinc-500 text-sm">
        Correlation engine data unavailable.
      </p>
    );
  }

  const labels = correlation.matrix_labels;
  const matrix = correlation.matrix_values ?? [];
  const zMatrix = correlation.zscore_matrix_values ?? [];
  const instability = correlation.covariance_instability;
  const shift = correlation.regime_correlation_shift;
  const cells = correlation.heatmap_cells ?? [];

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3 text-xs uppercase tracking-[0.2em]">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
          <span className="text-zinc-500">Cov Instability</span>
          <p className="text-orange-400 font-bold mt-1">
            {instability?.regime ?? "--"}{" "}
            <span className="text-zinc-400 text-[10px]">
              ({instability?.score?.toFixed(3) ?? "--"})
            </span>
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
          <span className="text-zinc-500">Regime Shift</span>
          <p className="text-cyan-400 font-bold mt-1">
            {shift?.sensitivity ?? "--"}{" "}
            <span className="text-zinc-400 text-[10px]">
              ({shift?.shift_magnitude?.toFixed(3) ?? "--"})
            </span>
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
          <span className="text-zinc-500">HMM Regime</span>
          <p className="text-yellow-300 font-bold mt-1">
            {shift?.current_regime ?? "--"}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] border-collapse text-center">
          <thead>
            <tr>
              <th className="p-2 text-zinc-500 text-xs" />
              {labels.map((label) => (
                <th
                  key={label}
                  className="p-2 text-zinc-400 text-xs font-mono"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((rowLabel, rowIdx) => (
              <tr key={rowLabel}>
                <td className="p-2 text-zinc-400 text-xs font-mono text-left">
                  {rowLabel}
                </td>
                {labels.map((_, colIdx) => {
                  const corr = matrix[rowIdx]?.[colIdx] ?? null;
                  const z = zMatrix[rowIdx]?.[colIdx] ?? 0;
                  return (
                    <td key={`${rowLabel}-${colIdx}`} className="p-1">
                      <div
                        className="rounded-md px-1 py-2 border border-zinc-800"
                        style={{
                          background: cellColor(z, "zscore"),
                        }}
                        title={`ρ=${corr ?? "--"} | z=${z.toFixed(2)}`}
                      >
                        <span className="text-[10px] font-mono text-zinc-100">
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

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {cells.map((cell) => {
          const positive = cell.daily_return_pct >= 0;
          return (
            <div
              key={cell.asset}
              className="bg-zinc-900 rounded-xl p-4 border border-zinc-800"
            >
              <p className="text-zinc-500 text-sm">{cell.asset}</p>
              <p
                className={`text-xl font-bold mt-1 ${
                  positive ? "text-green-400" : "text-red-400"
                }`}
              >
                {positive ? "+" : ""}
                {cell.daily_return_pct.toFixed(2)}%
              </p>
              <p className="text-[10px] text-zinc-500 mt-2 font-mono">
                β BTC {cell.beta_vs_btc.toFixed(2)}
              </p>
              <p className="text-[10px] text-cyan-400 font-mono">
                ρz BTC {cell.correlation_zscore_vs_btc.toFixed(2)}
              </p>
            </div>
          );
        })}
      </div>

      {shift?.largest_shifts?.length ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <p className="text-zinc-500 text-xs uppercase tracking-[0.2em] mb-3">
            Regime-Sensitive Correlation Shifts
          </p>
          <div className="space-y-2">
            {shift.largest_shifts.map((item) => (
              <div
                key={item.pair}
                className="flex justify-between text-sm font-mono"
              >
                <span className="text-zinc-400">{item.pair}</span>
                <span
                  className={
                    item.delta >= 0 ? "text-green-400" : "text-red-400"
                  }
                >
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
