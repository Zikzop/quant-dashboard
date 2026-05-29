"use client";

import { C, statusColor, proximityColor, pnlColor } from "@/lib/colors";
import { fmt, fmtPct, fmtUsd, fmtSign } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  ProximityBar,
  KillSwitch,
  StatusBadge,
  Divider,
  AlertStrip,
  Sparkline,
} from "@/components/ui/primitives";
import { useRiskStore } from "@/state/stores/useRiskStore";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useDecision } from "@/hooks/useDecision";

function PropFirmDeathWidget() {
  const pf = useRiskStore((s) => s.propFirm);
  const color = statusColor(pf.status);
  const dailyPct = pf.daily_proximity_pct;
  const maxPct = pf.max_proximity_pct;

  return (
    <Panel
      label="DISTANCE TO PROP FIRM DEATH"
      accent={color}
      tag="CRITICAL"
    >
      <div className="flex items-center gap-2 mb-3">
        <StatusBadge label={pf.status} color={color} pulse={pf.status === "CRITICAL" || pf.status === "DANGER"} />
        <div className="flex-1" />
        <div
          style={{
            fontSize: 20,
            fontFamily: "'IBM Plex Mono', monospace",
            fontWeight: 800,
            color,
            letterSpacing: "-0.02em",
          }}
        >
          {fmtPct(Math.max(dailyPct, maxPct))}
        </div>
      </div>

      <div className="space-y-3 mb-3">
        <ProximityBar
          label="DAILY LOSS"
          consumed={pf.current_daily_loss}
          total={pf.daily_loss_limit}
          color={proximityColor(dailyPct)}
        />
        <ProximityBar
          label="MAX LOSS"
          consumed={pf.current_total_loss}
          total={pf.max_loss_limit}
          color={proximityColor(maxPct)}
        />
      </div>

      <Divider label="LIMITS" />

      <div className="space-y-0.5">
        <StatRow label="REMAINING DAILY" value={fmtUsd(pf.remaining_daily_loss)} accent={C.safe} />
        <StatRow label="REMAINING MAX" value={fmtUsd(pf.remaining_max_loss)} accent={C.safe} />
        <StatRow label="STRESS ESTIMATE" value={fmtUsd(pf.stress_estimate)} accent={C.warning} sub="1σ SHOCK" />
        <StatRow label="DAILY LIMIT" value={fmtUsd(pf.daily_loss_limit)} />
        <StatRow label="MAX LIMIT" value={fmtUsd(pf.max_loss_limit)} />
      </div>

      {pf.stress_estimate > pf.remaining_daily_loss && (
        <div className="mt-2">
          <AlertStrip
            text="STRESS ESTIMATE EXCEEDS REMAINING DAILY ALLOWANCE"
            severity="critical"
          />
        </div>
      )}
    </Panel>
  );
}

function PortfolioExposurePanel() {
  const risk = useRiskStore((s) => s.portfolioRisk);

  return (
    <Panel label="PORTFOLIO EXPOSURE" accent={C.blue}>
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell label="GROSS" value={fmtUsd(risk.gross_exposure, 0)} accent={C.t1} large />
        <StatCell label="NET" value={fmtUsd(risk.net_exposure, 0)} accent={risk.net_exposure > 0 ? C.bullish : C.bearish} large />
        <StatCell label="LEVERAGE" value={`${fmt(risk.leverage, 1)}x`} accent={risk.leverage > 3 ? C.danger : C.warning} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="LONG EXPOSURE" value={fmtUsd(risk.long_exposure, 0)} accent={C.bullish} />
        <StatRow label="SHORT EXPOSURE" value={fmtUsd(risk.short_exposure, 0)} accent={C.bearish} />
        <StatRow label="BETA EXPOSURE" value={fmt(risk.beta_exposure, 2)} accent={risk.beta_exposure > 1 ? C.warning : C.t1} />
      </div>
    </Panel>
  );
}

function DrawdownPanel() {
  const dd = useRiskStore((s) => s.drawdown);

  return (
    <Panel label="DRAWDOWN MONITOR" accent={C.bearish}>
      <div className="grid grid-cols-3 gap-1 mb-2">
        <StatCell label="DAILY DD" value={fmtPct(dd.daily_drawdown)} accent={C.bearish} large />
        <StatCell label="WEEKLY DD" value={fmtPct(dd.weekly_drawdown)} accent={C.bearish} large />
        <StatCell label="MAX DD" value={fmtPct(dd.max_drawdown)} accent={C.critical} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="DAILY HWM" value={fmtUsd(dd.daily_high_water, 0)} />
        <StatRow label="WEEKLY HWM" value={fmtUsd(dd.weekly_high_water, 0)} />
        <StatRow label="UNDERWATER" value={`${dd.underwater_duration}d`} accent={dd.underwater_duration > 5 ? C.danger : C.t1} />
      </div>
    </Panel>
  );
}

function KillSwitchPanel() {
  const ks = useRiskStore((s) => s.killSwitch);
  const toggleGlobal = useRiskStore((s) => s.toggleGlobalKill);

  return (
    <Panel label="KILL SWITCH STATUS" accent={ks.global_kill ? C.critical : C.safe} tag={ks.global_kill ? "ACTIVE" : "STANDBY"}>
      {ks.global_kill && (
        <AlertStrip text="GLOBAL KILL SWITCH ACTIVE — ALL TRADING HALTED" severity="critical" />
      )}
      <div className="space-y-1 mt-1">
        <KillSwitch label="VOLATILITY KILL" active={ks.volatility_kill.active} triggered={ks.volatility_kill.triggered} />
        <KillSwitch label="MAX DRAWDOWN KILL" active={ks.drawdown_kill.active} triggered={ks.drawdown_kill.triggered} />
        <KillSwitch label="EXECUTION ANOMALY" active={ks.execution_kill.active} triggered={ks.execution_kill.triggered} />
      </div>
      <Divider />
      <div className="space-y-0.5">
        <StatRow label="VOL THRESHOLD" value={`${ks.volatility_kill.threshold}%`} sub={`NOW ${fmt(ks.volatility_kill.current)}%`} />
        <StatRow label="DD THRESHOLD" value={`${ks.drawdown_kill.threshold}%`} sub={`NOW ${fmt(ks.drawdown_kill.current)}%`} />
        <StatRow label="ANOMALIES" value={`${ks.execution_kill.anomaly_count}`} accent={ks.execution_kill.anomaly_count > 0 ? C.warning : C.t1} />
      </div>
      <button
        onClick={toggleGlobal}
        className="w-full mt-2 py-1.5 text-center transition-colors"
        style={{
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.15em",
          fontFamily: "'IBM Plex Mono', monospace",
          color: ks.global_kill ? C.safe : C.critical,
          background: ks.global_kill ? "rgba(34,197,94,0.08)" : "rgba(220,38,38,0.08)",
          border: `1px solid ${ks.global_kill ? C.safe : C.critical}`,
          cursor: "pointer",
        }}
      >
        {ks.global_kill ? "DISENGAGE KILL SWITCH" : "ENGAGE GLOBAL KILL"}
      </button>
    </Panel>
  );
}

function RiskMetricsPanel() {
  const rm = useRiskStore((s) => s.riskMetrics);

  return (
    <Panel label="RISK METRICS" accent={C.purple}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="VaR 95" value={fmtUsd(rm.var_95, 0)} accent={C.bearish} />
        <StatCell label="VaR 99" value={fmtUsd(rm.var_99, 0)} accent={C.critical} />
        <StatCell label="CVaR 95" value={fmtUsd(rm.cvar_95, 0)} accent={C.bearish} />
        <StatCell label="CVaR 99" value={fmtUsd(rm.cvar_99, 0)} accent={C.critical} />
      </div>
      <Divider label="RATIOS" />
      <div className="space-y-0.5">
        <StatRow label="SHARPE" value={fmt(rm.sharpe_ratio)} accent={rm.sharpe_ratio > 1 ? C.bullish : C.warning} />
        <StatRow label="SORTINO" value={fmt(rm.sortino_ratio)} accent={rm.sortino_ratio > 1.5 ? C.bullish : C.warning} />
        <StatRow label="CALMAR" value={fmt(rm.calmar_ratio)} accent={rm.calmar_ratio > 1 ? C.bullish : C.warning} />
      </div>
    </Panel>
  );
}

function CorrelationRiskPanel() {
  const cr = useRiskStore((s) => s.correlationRisk);

  return (
    <Panel label="CORRELATION RISK" accent={C.volatile}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="MAX CORR" value={fmt(cr.max_correlation)} accent={cr.max_correlation > 0.7 ? C.danger : C.t1} />
        <StatCell label="CONCENTRATION" value={fmt(cr.concentration_score)} accent={cr.concentration_score > 0.5 ? C.danger : C.t1} />
      </div>
      <Divider label="CORRELATED PAIRS" />
      <div className="space-y-0.5">
        {cr.correlated_pairs.map((p) => (
          <StatRow
            key={p.pair}
            label={p.pair}
            value={fmt(p.correlation)}
            accent={p.correlation > 0.7 ? C.danger : p.correlation > 0.5 ? C.warning : C.t1}
          />
        ))}
      </div>
      <Divider />
      <StatRow label="HIDDEN FACTOR EXP." value={fmt(cr.hidden_factor_exposure)} accent={cr.hidden_factor_exposure > 0.3 ? C.warning : C.t1} />
    </Panel>
  );
}

function TailRiskPanel() {
  const rm = useRiskStore((s) => s.riskMetrics);
  const market = useMarketStore((s) => s.market);
  const decision = useDecision(market);

  return (
    <Panel label="TAIL RISK & EXPECTED SHORTFALL" accent={C.critical}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="ES 95 (CVaR)" value={fmtUsd(rm.cvar_95, 0)} accent={C.bearish} large />
        <StatCell label="ES 99" value={fmtUsd(rm.cvar_99, 0)} accent={C.critical} large />
      </div>
      {decision && (
        <>
          <Divider label="REGIME-CONDITIONED" />
          <StatRow label="TAIL RISK" value={decision.risk.tailRisk.replace(/_/g, " ")} accent={decision.risk.tailRisk === "LOW" ? C.bullish : C.danger} />
          <StatRow label="KURTOSIS" value={fmt(decision.risk.tailKurtosis, 2)} sub="excess" />
          <StatRow label="SKEW" value={fmt(decision.risk.skew, 2)} />
        </>
      )}
    </Panel>
  );
}

function RegimeRiskPanel() {
  const market = useMarketStore((s) => s.market);
  const decision = useDecision(market);

  if (!decision) {
    return (
      <Panel label="REGIME RISK" accent={C.purple}>
        <span style={{ fontSize: 10, color: C.t2 }}>Awaiting regime data...</span>
      </Panel>
    );
  }

  const stabColor = decision.transition.stability === "STABLE" ? C.bullish : decision.transition.stability === "FRAGILE" ? C.warning : C.danger;

  return (
    <Panel label="REGIME RISK" accent={C.purple} tag={decision.transition.stability}>
      <StatRow label="CURRENT REGIME" value={decision.transition.current.replace(/_/g, " ")} />
      <StatRow label="TRANSITION PROB" value={`${(decision.transition.transitionProbability * 100).toFixed(0)}%`} accent={stabColor} />
      <StatRow label="INSTABILITY" value={`${(decision.transition.instability * 100).toFixed(0)}%`} accent={stabColor} />
      <StatRow label="LIFECYCLE PHASE" value={decision.lifecycle.phaseLabel} accent={C.amber} />
      <StatRow label="UNCERTAINTY" value={decision.uncertaintyLevel} accent={decision.uncertaintyLevel === "LOW" ? C.bullish : C.warning} />
    </Panel>
  );
}

export default function RiskCommandCenter() {
  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div
        className="flex items-center px-4"
        style={{ height: 32, borderBottom: `1px solid ${C.border}`, background: C.surface }}
      >
        <span style={{ fontSize: 10, color: C.t1, letterSpacing: "0.14em", fontWeight: 700 }}>
          RISK GOVERNANCE · VaR · CVaR · DRAWDOWN · REGIME RISK · TAIL RISK
        </span>
      </div>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        {/* Top: Prop Firm Death — full width critical widget */}
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <PropFirmDeathWidget />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <PortfolioExposurePanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <DrawdownPanel />
        </div>

        {/* Bottom row */}
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <KillSwitchPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <RiskMetricsPanel />
        </div>
        <div className="col-span-12 lg:col-span-4" style={{ background: C.bg }}>
          <CorrelationRiskPanel />
        </div>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <TailRiskPanel />
        </div>
        <div className="col-span-12 lg:col-span-6" style={{ background: C.bg }}>
          <RegimeRiskPanel />
        </div>
      </div>
    </div>
  );
}
