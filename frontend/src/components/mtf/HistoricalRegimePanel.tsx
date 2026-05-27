"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct } from "@/lib/format";
import { Panel, StatRow, StatCell, Divider, ProgressBar, AlertStrip } from "@/components/ui/primitives";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

export default function HistoricalRegimePanel() {
  const ctx = useTimeframeStore((s) => s.historicalContext);
  const rColor = regimeColor(ctx.current_regime);

  return (
    <Panel
      label="HISTORICAL REGIME INTELLIGENCE"
      accent={rColor}
      tag={ctx.current_regime.replace(/_/g, " ")}
    >
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell
          label="SIMILAR REGIMES"
          value={`${ctx.similar_regime_count}`}
          accent={ctx.similar_regime_count > 3 ? C.bullish : C.warning}
        />
        <StatCell
          label="HIST WIN RATE"
          value={`${fmt(ctx.historical_win_rate, 0)}%`}
          accent={ctx.historical_win_rate > 55 ? C.bullish : ctx.historical_win_rate > 45 ? C.warning : C.bearish}
        />
        <StatCell
          label="HIST AVG RETURN"
          value={`${ctx.historical_avg_return >= 0 ? "+" : ""}${fmt(ctx.historical_avg_return)}%`}
          accent={ctx.historical_avg_return >= 0 ? C.bullish : C.bearish}
        />
      </div>

      <div className="space-y-0.5">
        <StatRow label="AVG VOL AFTER" value={fmt(ctx.historical_avg_vol_after, 4)} accent={C.volatile} />
        <StatRow label="HIST MAX DD" value={`${fmt(ctx.historical_max_drawdown)}%`} accent={C.bearish} />
      </div>

      <Divider label="ALL REGIMES" />

      {ctx.regime_stats.length > 0 ? (
        <div className="space-y-2">
          {ctx.regime_stats.map((rs) => {
            const isCurrentRegime = rs.regime === ctx.current_regime;
            const rsColor = regimeColor(rs.regime);
            return (
              <div
                key={rs.regime}
                style={{
                  background: isCurrentRegime ? `${rsColor}08` : "transparent",
                  borderLeft: isCurrentRegime ? `2px solid ${rsColor}` : "2px solid transparent",
                  padding: "4px 6px",
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span style={{ fontSize: 9, fontWeight: 700, color: rsColor, letterSpacing: "0.04em" }}>
                    {rs.regime.replace(/_/g, " ")}
                    {isCurrentRegime && (
                      <span style={{ fontSize: 7, color: C.t3, marginLeft: 4 }}>CURRENT</span>
                    )}
                  </span>
                  <span style={{ fontSize: 8, color: C.t3, fontFamily: "'IBM Plex Mono', monospace" }}>
                    {rs.occurrences}x
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-x-2" style={{ fontSize: 8 }}>
                  <div>
                    <span style={{ color: C.t3 }}>WR </span>
                    <span style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600,
                      color: rs.win_rate > 55 ? C.bullish : rs.win_rate > 45 ? C.t1 : C.bearish,
                    }}>
                      {fmt(rs.win_rate, 0)}%
                    </span>
                  </div>
                  <div>
                    <span style={{ color: C.t3 }}>RET </span>
                    <span style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600,
                      color: rs.avg_return_pct >= 0 ? C.bullish : C.bearish,
                    }}>
                      {rs.avg_return_pct >= 0 ? "+" : ""}{fmt(rs.avg_return_pct)}%
                    </span>
                  </div>
                  <div>
                    <span style={{ color: C.t3 }}>DUR </span>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", color: C.t1 }}>
                      {fmt(rs.avg_duration_bars, 0)}b
                    </span>
                  </div>
                  <div>
                    <span style={{ color: C.t3 }}>DD </span>
                    <span style={{ fontFamily: "'IBM Plex Mono', monospace", color: C.bearish }}>
                      {fmt(rs.avg_drawdown)}%
                    </span>
                  </div>
                </div>
                {rs.transition_to.length > 0 && (
                  <div className="flex items-center gap-2 mt-1">
                    <span style={{ fontSize: 7, color: C.t3, letterSpacing: "0.06em" }}>NEXT →</span>
                    {rs.transition_to.slice(0, 3).map((t) => (
                      <span key={t.regime} style={{
                        fontSize: 7, fontFamily: "'IBM Plex Mono', monospace",
                        color: regimeColor(t.regime),
                      }}>
                        {t.regime.replace(/_/g, " ")} {(t.probability * 100).toFixed(0)}%
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <span style={{ fontSize: 9, color: C.t3 }}>Insufficient historical data</span>
      )}

      {ctx.historical_win_rate < 45 && ctx.similar_regime_count > 2 && (
        <div className="mt-2">
          <AlertStrip
            text="HISTORICALLY WEAK REGIME — REDUCE POSITION SIZING"
            severity="warning"
          />
        </div>
      )}

      <Divider label="REGIME TIMELINE" />
      <div className="flex gap-px overflow-hidden" style={{ height: 12 }}>
        {ctx.regime_history.slice(-30).map((h, i) => (
          <div
            key={i}
            className="flex-1"
            style={{
              background: regimeColor(h.regime),
              opacity: 0.6,
              minWidth: 2,
            }}
            title={`${h.regime} (${h.duration} bars)`}
          />
        ))}
      </div>
    </Panel>
  );
}
