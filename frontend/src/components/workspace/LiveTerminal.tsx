"use client";

import { C, pnlColor, regimeColor, statusColor } from "@/lib/colors";
import { fmt, fmtPct, fmtUsd, fmtSign } from "@/lib/format";
import {
  Panel,
  StatRow,
  StatCell,
  StatusBadge,
  KillSwitch,
  Divider,
  AlertStrip,
  MiniTable,
} from "@/components/ui/primitives";
import { usePortfolioStore } from "@/state/stores/usePortfolioStore";
import { useRiskStore } from "@/state/stores/useRiskStore";
import { useMarketStore } from "@/state/stores/useMarketStore";

function PositionsPanel() {
  const positions = usePortfolioStore((s) => s.positions);
  const totalPnl = usePortfolioStore((s) => s.totalPnl);

  return (
    <Panel label="CURRENT POSITIONS" accent={C.t1} tag={`PnL ${fmtSign(totalPnl, 0)}`}>
      <MiniTable
        headers={["SYMBOL", "SIDE", "SIZE", "ENTRY", "CURRENT", "UNREAL", "REAL", "LEV"]}
        rows={positions.map((p) => ({
          cells: [
            { value: p.symbol },
            { value: p.side, accent: p.side === "LONG" ? C.bullish : C.bearish },
            { value: fmt(p.size, p.size < 1 ? 4 : 1) },
            { value: fmtUsd(p.entry_price, 1) },
            { value: fmtUsd(p.current_price, 1) },
            { value: fmtSign(p.unrealized_pnl, 0), accent: pnlColor(p.unrealized_pnl) },
            { value: fmtSign(p.realized_pnl, 0), accent: pnlColor(p.realized_pnl) },
            { value: `${p.leverage}x` },
          ],
        }))}
      />
    </Panel>
  );
}

function LivePnlPanel() {
  const totalPnl = usePortfolioStore((s) => s.totalPnl);
  const risk = useRiskStore((s) => s.portfolioRisk);
  const pf = useRiskStore((s) => s.propFirm);

  return (
    <Panel label="LIVE PnL" accent={pnlColor(totalPnl)}>
      <div
        style={{
          fontSize: 32,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 800,
          color: pnlColor(totalPnl),
          letterSpacing: "-0.03em",
          lineHeight: 1,
          marginBottom: 8,
        }}
      >
        {totalPnl >= 0 ? "+" : ""}{fmtUsd(totalPnl, 0)}
      </div>
      <div className="space-y-0.5">
        <StatRow label="NET EXPOSURE" value={fmtUsd(risk.net_exposure, 0)} accent={risk.net_exposure > 0 ? C.bullish : C.bearish} />
        <StatRow label="LEVERAGE" value={`${fmt(risk.leverage, 1)}x`} accent={risk.leverage > 3 ? C.danger : C.warning} />
        <StatRow label="PROP FIRM STATUS" value={pf.status} accent={statusColor(pf.status)} />
      </div>
    </Panel>
  );
}

function RegimeStatePanel() {
  const market = useMarketStore((s) => s.market);
  const state = market?.market_state;

  return (
    <Panel label="REGIME STATE" accent={regimeColor(state?.market_regime)}>
      <div className="grid grid-cols-2 gap-1 mb-2">
        <StatCell label="REGIME" value={state?.market_regime ?? "--"} accent={regimeColor(state?.market_regime)} large />
        <StatCell label="HMM STATE" value={market?.hmm_regime ?? "--"} accent={regimeColor(market?.hmm_regime)} large />
      </div>
      <div className="space-y-0.5">
        <StatRow label="VOL REGIME" value={state?.volatility_regime ?? "--"} accent={regimeColor(state?.volatility_regime)} />
        <StatRow label="TREND STR" value={state?.trend_strength ?? "--"} />
        <StatRow label="DIRECTION" value={state?.direction ?? "--"} accent={
          state?.direction?.toUpperCase().includes("BULL") ? C.bullish :
          state?.direction?.toUpperCase().includes("BEAR") ? C.bearish : C.neutral
        } />
      </div>
    </Panel>
  );
}

function RiskAlertsPanel() {
  const pf = useRiskStore((s) => s.propFirm);
  const ks = useRiskStore((s) => s.killSwitch);
  const dd = useRiskStore((s) => s.drawdown);

  const alerts: Array<{ text: string; severity: "info" | "warning" | "danger" | "critical" }> = [];

  if (ks.global_kill) alerts.push({ text: "GLOBAL KILL SWITCH ACTIVE", severity: "critical" });
  if (ks.volatility_kill.triggered) alerts.push({ text: "VOLATILITY KILL TRIGGERED", severity: "critical" });
  if (ks.drawdown_kill.triggered) alerts.push({ text: "DRAWDOWN KILL TRIGGERED", severity: "critical" });
  if (pf.daily_proximity_pct > 60) alerts.push({ text: `DAILY LOSS AT ${fmt(pf.daily_proximity_pct, 0)}% OF LIMIT`, severity: "danger" });
  if (pf.max_proximity_pct > 50) alerts.push({ text: `MAX LOSS AT ${fmt(pf.max_proximity_pct, 0)}% OF LIMIT`, severity: "warning" });
  if (dd.daily_drawdown < -3) alerts.push({ text: "DAILY DRAWDOWN EXCEEDS 3%", severity: "danger" });
  if (alerts.length === 0) alerts.push({ text: "ALL SYSTEMS NOMINAL", severity: "info" });

  return (
    <Panel label="RISK ALERTS" accent={alerts[0].severity === "info" ? C.safe : C.danger}>
      <div className="space-y-1">
        {alerts.map((a, i) => (
          <AlertStrip key={i} text={a.text} severity={a.severity} />
        ))}
      </div>
    </Panel>
  );
}

function KillSwitchControlPanel() {
  const ks = useRiskStore((s) => s.killSwitch);
  const toggleGlobal = useRiskStore((s) => s.toggleGlobalKill);

  return (
    <Panel label="KILL SWITCH CONTROLS" accent={ks.global_kill ? C.critical : C.safe}>
      <div className="space-y-1">
        <KillSwitch label="VOLATILITY" active={ks.volatility_kill.active} triggered={ks.volatility_kill.triggered} />
        <KillSwitch label="DRAWDOWN" active={ks.drawdown_kill.active} triggered={ks.drawdown_kill.triggered} />
        <KillSwitch label="EXECUTION" active={ks.execution_kill.active} triggered={ks.execution_kill.triggered} />
      </div>
      <button
        onClick={toggleGlobal}
        className="w-full mt-2 py-2 text-center"
        style={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: "0.15em",
          fontFamily: "'IBM Plex Mono', monospace",
          color: ks.global_kill ? C.safe : C.critical,
          background: ks.global_kill ? "rgba(34,197,94,0.08)" : "rgba(220,38,38,0.08)",
          border: `1px solid ${ks.global_kill ? C.safe : C.critical}`,
          cursor: "pointer",
        }}
      >
        {ks.global_kill ? "⬒ DISENGAGE KILL SWITCH" : "⬒ ENGAGE GLOBAL KILL"}
      </button>
    </Panel>
  );
}

export default function LiveTerminal() {
  return (
    <div className="h-full overflow-auto" style={{ background: C.bg2 }}>
      <div className="grid grid-cols-12 gap-px p-1" style={{ background: C.border }}>
        <div className="col-span-12" style={{ background: C.bg }}>
          <PositionsPanel />
        </div>
        <div className="col-span-12 lg:col-span-3" style={{ background: C.bg }}>
          <LivePnlPanel />
        </div>
        <div className="col-span-12 lg:col-span-3" style={{ background: C.bg }}>
          <RegimeStatePanel />
        </div>
        <div className="col-span-12 lg:col-span-3" style={{ background: C.bg }}>
          <RiskAlertsPanel />
        </div>
        <div className="col-span-12 lg:col-span-3" style={{ background: C.bg }}>
          <KillSwitchControlPanel />
        </div>
      </div>
    </div>
  );
}
