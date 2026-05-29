"use client";

import { C, pnlColor } from "@/lib/colors";
import { fmt, fmtPct, fmtUsd, fmtSign } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  ProgressBar,
  Divider,
  Sparkline,
} from "@/components/ui/primitives";
import { usePortfolioStore } from "@/state/stores/usePortfolioStore";
import { useRiskStore } from "@/state/stores/useRiskStore";

function AllocationByAssetPanel() {
  const alloc = usePortfolioStore((s) => s.allocation);

  return (
    <Panel label="ALLOCATION BY ASSET" accent={C.blue}>
      <div className="space-y-1.5">
        {alloc.by_asset.map((a) => (
          <div key={a.asset}>
            <div className="flex items-center justify-between mb-0.5">
              <span style={{ fontSize: 10, color: C.t2 }}>{a.asset}</span>
              <div className="flex items-center gap-3">
                <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", color: pnlColor(a.pnl), fontWeight: 600 }}>
                  {fmtSign(a.pnl, 0)}
                </span>
                <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", color: C.t1 }}>
                  {fmtPct(a.weight)}
                </span>
              </div>
            </div>
            <div className="w-full h-[3px]" style={{ background: C.surface2 }}>
              <div className="h-full" style={{ width: `${a.weight * 100}%`, background: C.blue }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function AllocationByStrategyPanel() {
  const alloc = usePortfolioStore((s) => s.allocation);

  return (
    <Panel label="ALLOCATION BY STRATEGY" accent={C.purple}>
      <div className="space-y-1.5">
        {alloc.by_strategy.map((s) => (
          <div key={s.strategy}>
            <div className="flex items-center justify-between mb-0.5">
              <span style={{ fontSize: 10, color: C.t2 }}>{s.strategy}</span>
              <div className="flex items-center gap-3">
                <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", color: pnlColor(s.pnl), fontWeight: 600 }}>
                  {fmtSign(s.pnl, 0)}
                </span>
                <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", color: C.t1 }}>
                  {fmtPct(s.weight)}
                </span>
              </div>
            </div>
            <div className="w-full h-[3px]" style={{ background: C.surface2 }}>
              <div className="h-full" style={{ width: `${s.weight * 100}%`, background: C.purple }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function VolContributionPanel() {
  const alloc = usePortfolioStore((s) => s.allocation);

  return (
    <Panel label="VOLATILITY CONTRIBUTION" accent={C.volatile}>
      <div className="space-y-1">
        {alloc.by_vol_contribution.map((v) => (
          <ProgressBar
            key={v.source}
            label={v.source.replace("-PERP", "")}
            value={v.vol_contribution}
            color={v.vol_contribution > 0.3 ? C.danger : C.volatile}
          />
        ))}
      </div>
    </Panel>
  );
}

function PerformanceAttributionPanel() {
  const attr = usePortfolioStore((s) => s.attribution);

  return (
    <Panel label="PERFORMANCE ATTRIBUTION" accent={C.bullish}>
      <Divider label="RETURN CONTRIBUTORS" />
      <div className="space-y-0.5 mb-2">
        {attr.return_contributors.map((c) => (
          <StatRow key={c.source} label={c.source} value={`+${fmt(c.contribution)}%`} accent={C.bullish} />
        ))}
      </div>
      <Divider label="LOSS CONTRIBUTORS" />
      <div className="space-y-0.5">
        {attr.loss_contributors.map((c) => (
          <StatRow key={c.source} label={c.source} value={`${fmt(c.contribution)}%`} accent={C.bearish} />
        ))}
      </div>
    </Panel>
  );
}

function RiskContributionPanel() {
  const rc = usePortfolioStore((s) => s.riskContribution);

  return (
    <Panel label="RISK CONTRIBUTION" accent={C.danger} tag={`DOMINANT: ${rc.dominant_factor}`}>
      <div className="space-y-1">
        {rc.contributors.map((c) => (
          <div key={c.source}>
            <div className="flex items-center justify-between mb-0.5">
              <span style={{ fontSize: 10, color: C.t2 }}>{c.source}</span>
              <div className="flex items-center gap-3">
                <span style={{ fontSize: 9, fontFamily: "'IBM Plex Mono', monospace", color: C.t3 }}>
                  mVaR {fmtUsd(c.marginal_var, 0)}
                </span>
                <span style={{ fontSize: 10, fontFamily: "'IBM Plex Mono', monospace", color: c.risk_pct > 30 ? C.danger : C.t1, fontWeight: 600 }}>
                  {c.risk_pct}%
                </span>
              </div>
            </div>
            <div className="w-full h-[3px]" style={{ background: C.surface2 }}>
              <div className="h-full" style={{ width: `${c.risk_pct}%`, background: c.risk_pct > 30 ? C.danger : C.warning }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function EquityCurvePanel() {
  const eq = usePortfolioStore((s) => s.equity);
  const values = eq.equity_curve.map((p) => p.value);

  return (
    <Panel label="EQUITY CURVE DIAGNOSTICS" accent={C.cyan}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="SMOOTHNESS" value={fmt(eq.smoothness)} accent={eq.smoothness > 0.6 ? C.safe : C.warning} />
        <StatCell label="EQUITY VOL" value={`${fmt(eq.equity_volatility)}%`} accent={eq.equity_volatility > 3 ? C.danger : C.t1} />
      </div>
      <Divider label="60D EQUITY CURVE" />
      <div className="py-1">
        <Sparkline data={values} width={320} height={40} color={C.cyan} />
      </div>
      <Divider label="UNDERWATER PERIODS" />
      <div className="space-y-0.5">
        {eq.underwater_periods.map((p, i) => (
          <StatRow
            key={i}
            label={`${p.start}${p.end ? ` → ${p.end}` : " → NOW"}`}
            value={`${fmt(p.depth)}%`}
            accent={C.bearish}
          />
        ))}
      </div>
    </Panel>
  );
}

function SummaryStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span style={{ fontSize: 9, color: C.t3, letterSpacing: "0.12em" }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: accent ?? C.t1 }}>
        {value}
      </span>
    </div>
  );
}

export default function PortfolioAnalytics() {
  const risk = useRiskStore((s) => s.portfolioRisk);

  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div
        className="flex items-center gap-6 px-4"
        style={{ height: 32, borderBottom: `1px solid ${C.border}`, background: C.surface }}
      >
        <SummaryStat label="NET EXP" value={fmtUsd(risk.net_exposure, 0)} accent={risk.net_exposure > 0 ? C.bullish : C.bearish} />
        <SummaryStat label="GROSS EXP" value={fmtUsd(risk.gross_exposure, 0)} />
        <SummaryStat label="LEVERAGE" value={`${fmt(risk.leverage, 1)}x`} accent={risk.leverage > 3 ? C.danger : C.t1} />
        <SummaryStat label="BETA EXP" value={fmt(risk.beta_exposure, 2)} />
      </div>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <AllocationByAssetPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <AllocationByStrategyPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <VolContributionPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <PerformanceAttributionPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <RiskContributionPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <EquityCurvePanel />
        </div>
      </div>
    </div>
  );
}
