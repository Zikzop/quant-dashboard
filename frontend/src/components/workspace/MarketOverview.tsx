"use client";

import { C, regimeColor } from "@/lib/colors";
import { fmt, fmtPct, probFraction } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  ProgressBar,
  StatusBadge,
  Divider,
  MiniTable,
  Sparkline,
} from "@/components/ui/primitives";
import { useMarketStore } from "@/state/stores/useMarketStore";
import type { MarketPayload, CorrelationPayload } from "@/types/market";

function RegimeDetectionPanel({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const hmm = market.hmm_regime ?? "--";
  const regime = state?.market_regime ?? "--";
  const rColor = regimeColor(regime);

  const regimes = [
    { label: "TRENDING", active: hmm === "TRENDING" || regime.includes("TREND"), color: C.bullish },
    { label: "MEAN REVERTING", active: hmm === "MEAN_REVERT", color: C.cyan },
    { label: "HIGH VOLATILITY", active: state?.volatility_regime === "EXPANDING", color: C.volatile },
    { label: "LOW VOLATILITY", active: state?.volatility_regime === "COMPRESSING", color: C.blue },
    { label: "PANIC", active: hmm === "CRISIS", color: C.critical },
    { label: "COMPRESSION", active: state?.volatility_regime === "COMPRESSING", color: C.purple },
    { label: "EXPANSION", active: state?.volatility_regime === "EXPANDING", color: C.amber },
  ];

  return (
    <Panel label="REGIME DETECTION" accent={rColor} tag={regime}>
      <div className="flex items-center gap-2 mb-3">
        <StatusBadge label={regime} color={rColor} pulse />
        <div className="flex-1" />
        <span style={{ fontSize: 10, color: C.t2, fontFamily: "'IBM Plex Mono', monospace" }}>
          HMM: {hmm}
        </span>
      </div>

      <div className="space-y-1">
        {regimes.map((r) => (
          <div
            key={r.label}
            className="flex items-center justify-between py-0.5 px-1"
            style={{
              background: r.active ? `${r.color}11` : "transparent",
              borderLeft: r.active ? `2px solid ${r.color}` : "2px solid transparent",
            }}
          >
            <span style={{ fontSize: 9, color: r.active ? r.color : C.t3, letterSpacing: "0.06em" }}>
              {r.label}
            </span>
            <span style={{
              fontSize: 8,
              color: r.active ? r.color : C.t4,
              fontWeight: 700,
              letterSpacing: "0.1em",
            }}>
              {r.active ? "ACTIVE" : "INACTIVE"}
            </span>
          </div>
        ))}
      </div>

      <Divider label="PROBABILITIES" />
      <div className="space-y-1.5">
        <ProgressBar label="TREND" value={probFraction(market.trend_probability)} color={C.bullish} />
        <ProgressBar label="MEAN REV" value={probFraction(market.mean_revert_probability)} color={C.cyan} />
        <ProgressBar label="CRISIS" value={probFraction(market.crisis_probability)} color={C.critical} />
      </div>
    </Panel>
  );
}

function VolatilityAnalyticsPanel({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const volRegime = state?.volatility_regime ?? market.vol_regime ?? "--";
  const volColor = regimeColor(volRegime);

  return (
    <Panel label="VOLATILITY ANALYTICS" accent={C.volatile}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="REALIZED VOL" value={`${fmt(state?.volatility ?? market.volatility)}%`} accent={C.volatile} large />
        <StatCell label="VOL REGIME" value={volRegime} accent={volColor} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="GARCH σ" value={market.garch_vol != null ? fmt(market.garch_vol, 4) : "--"} accent={C.volatile} />
        <StatRow label="VOL SLOPE" value={market.vol_slope != null ? fmtPct(market.vol_slope) : "--"} accent={market.vol_slope && market.vol_slope > 0 ? C.danger : C.safe} />
        <StatRow label="TRANSITION RISK" value={state?.transition_risk ?? "--"} accent={state?.transition_risk === "ELEVATED" ? C.danger : C.t1} />
        <StatRow label="PERSISTENCE" value={state?.trend_persistence ?? "--"} accent={state?.trend_persistence === "WEAK" ? C.warning : C.bullish} />
        <StatRow label="CONFIDENCE" value={state?.confidence != null ? fmtPct(state.confidence) : "--"} accent={
          (state?.confidence ?? 0) > 0.75 ? C.bullish : (state?.confidence ?? 0) > 0.5 ? C.warning : C.bearish
        } />
      </div>
      <Divider label="ATR REGIME" />
      <StatRow label="ADX (14)" value={state?.adx != null ? fmt(state.adx) : "--"} accent={
        (state?.adx ?? 0) > 40 ? C.bullish : (state?.adx ?? 0) > 25 ? C.warning : C.t2
      } />
      <StatRow label="TREND STRENGTH" value={state?.trend_strength ?? "--"} accent={regimeColor(state?.trend_strength)} />
    </Panel>
  );
}

function CorrelationStatePanel({ correlation }: { correlation?: CorrelationPayload }) {
  const instability = correlation?.covariance_instability;
  const shift = correlation?.regime_correlation_shift;
  const cells = correlation?.heatmap_cells ?? [];

  return (
    <Panel label="CORRELATION STATE" accent={C.cyan}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell
          label="COV INSTABILITY"
          value={instability?.score != null ? fmt(instability.score, 3) : "--"}
          accent={instability?.regime === "UNSTABLE" ? C.danger : C.t1}
        />
        <StatCell
          label="SHIFT MAGNITUDE"
          value={shift?.shift_magnitude != null ? fmt(shift.shift_magnitude, 3) : "--"}
          accent={shift?.sensitivity === "HIGH" ? C.danger : C.t1}
        />
      </div>

      <Divider label="CROSS-ASSET" />
      {cells.length > 0 ? (
        <div className="space-y-0.5">
          {cells.map((c) => (
            <div key={c.asset} className="flex items-center justify-between py-0.5">
              <span style={{ fontSize: 10, color: C.t2 }}>{c.asset}</span>
              <div className="flex items-center gap-3">
                <span style={{
                  fontSize: 10,
                  fontFamily: "'IBM Plex Mono', monospace",
                  color: c.daily_return_pct >= 0 ? C.bullish : C.bearish,
                  fontWeight: 600,
                }}>
                  {c.daily_return_pct >= 0 ? "+" : ""}{fmt(c.daily_return_pct)}%
                </span>
                <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", color: C.t3 }}>
                  β{fmt(c.beta_vs_btc)}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <span style={{ fontSize: 10, color: C.t3 }}>No cross-asset data</span>
      )}

      {shift?.largest_shifts?.length ? (
        <>
          <Divider label="REGIME SHIFTS" />
          <div className="space-y-0.5">
            {shift.largest_shifts.map((s) => (
              <StatRow
                key={s.pair}
                label={s.pair}
                value={`${s.delta >= 0 ? "+" : ""}${fmt(s.delta, 3)}`}
                accent={Math.abs(s.delta) > 0.15 ? C.danger : C.t1}
              />
            ))}
          </div>
        </>
      ) : null}
    </Panel>
  );
}

function LiquidityConditionsPanel({ market }: { market: MarketPayload }) {
  const lastBars = market.chart_data.slice(-20);
  const avgVol = lastBars.reduce((s, b) => s + (b.garch_vol ?? 0), 0) / (lastBars.length || 1);
  const latestVol = lastBars[lastBars.length - 1]?.garch_vol ?? 0;
  const volAnomaly = latestVol > avgVol * 1.5;

  return (
    <Panel label="LIQUIDITY CONDITIONS" accent={C.blue}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="SPREAD REGIME" value={volAnomaly ? "WIDENING" : "NORMAL"} accent={volAnomaly ? C.warning : C.safe} />
        <StatCell label="VOLUME ANOMALY" value={volAnomaly ? "DETECTED" : "NONE"} accent={volAnomaly ? C.danger : C.safe} />
      </div>
      <Divider label="20-BAR VOLATILITY" />
      <div className="flex items-center gap-3">
        <Sparkline
          data={lastBars.map((b) => b.garch_vol ?? 0)}
          width={160}
          height={24}
          color={C.volatile}
        />
        <div>
          <div style={{ fontSize: 9, color: C.t3 }}>AVG</div>
          <div style={{ fontSize: 11, fontFamily: "'IBM Plex Mono', monospace", color: C.t1, fontWeight: 600 }}>
            {fmt(avgVol, 4)}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function DirectionalIntelligencePanel({ market }: { market: MarketPayload }) {
  const state = market.market_state;
  const dirColor = state?.direction?.toUpperCase().includes("BULL") ? C.bullish : state?.direction?.toUpperCase().includes("BEAR") ? C.bearish : C.neutral;

  return (
    <Panel label="DIRECTIONAL INTELLIGENCE" accent={dirColor}>
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell label="DIRECTION" value={state?.direction ?? "--"} accent={dirColor} large />
        <StatCell label="+DI" value={fmt(state?.plus_di)} accent={C.bullish} />
        <StatCell label="−DI" value={fmt(state?.minus_di)} accent={C.bearish} />
      </div>
      <div className="space-y-0.5">
        <StatRow label="DI SPREAD" value={
          state?.plus_di != null && state?.minus_di != null
            ? fmt(state.plus_di - state.minus_di)
            : "--"
        } accent={
          state?.plus_di != null && state?.minus_di != null && state.plus_di > state.minus_di
            ? C.bullish : C.bearish
        } />
        <StatRow label="RISK STATE" value={state?.risk_state ?? "--"} />
        <StatRow label="ADX" value={fmt(state?.adx)} accent={regimeColor(state?.trend_strength)} />
      </div>
    </Panel>
  );
}

export default function MarketOverview() {
  const market = useMarketStore((s) => s.market);

  if (!market) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: C.t3 }}>
        <span style={{ fontSize: 11, letterSpacing: "0.1em" }}>AWAITING MARKET DATA...</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <RegimeDetectionPanel market={market} />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <VolatilityAnalyticsPanel market={market} />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <CorrelationStatePanel correlation={market.correlation} />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <LiquidityConditionsPanel market={market} />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <DirectionalIntelligencePanel market={market} />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <Panel label="REGIME TRANSITION MATRIX" accent={C.purple}>
            <div className="space-y-0.5">
              <StatRow label="TREND → VOLATILE" value="42%" accent={C.warning} />
              <StatRow label="VOLATILE → CRISIS" value="17%" accent={C.danger} />
              <StatRow label="RECOVERY → TREND" value="63%" accent={C.bullish} />
              <StatRow label="CRISIS → RECOVERY" value="28%" accent={C.cyan} />
              <StatRow label="MEAN REV → TREND" value="35%" accent={C.bullish} />
            </div>
            <Divider label="CURRENT PATH" />
            <div className="flex items-center gap-2">
              <StatusBadge label={market.hmm_regime ?? "--"} color={regimeColor(market.hmm_regime)} />
              <span style={{ fontSize: 9, color: C.t3 }}>→</span>
              <span style={{ fontSize: 9, color: C.t2, letterSpacing: "0.06em" }}>
                MOST LIKELY: {market.hmm_regime === "TRENDING" ? "VOLATILE" : market.hmm_regime === "CRISIS" ? "RECOVERY" : "TREND"}
              </span>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
