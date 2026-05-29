"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef } from "react";

import TopBar from "../src/components/quant/TopBar";
import WorkspaceNav from "../src/components/workspace/WorkspaceNav";
import MarketIntelligenceStrip from "@/visualization/intelligence/MarketIntelligenceStrip";
import { MarketControlLayer } from "@/components/controls";
import { marketMatchesAsset } from "@/lib/assets/registry";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";
import { fetchMarketTimeframe } from "@/lib/api";
import { TIMEFRAMES } from "@/types/market";

const MainChart = dynamic(() => import("../src/components/quant/MainChart"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center" style={{ background: "#080809", color: "#6e6e7a", fontSize: 11, letterSpacing: "0.1em" }}>
      LOADING CHART ENGINE...
    </div>
  ),
});

const RiskCommandCenter = dynamic(() => import("../src/components/workspace/RiskCommandCenter"), { ssr: false });
const MarketOverview = dynamic(() => import("../src/components/workspace/MarketOverview"), { ssr: false });
const ExecutionMonitor = dynamic(() => import("../src/components/workspace/ExecutionMonitor"), { ssr: false });
const PortfolioAnalytics = dynamic(() => import("../src/components/workspace/PortfolioAnalytics"), { ssr: false });
const LiveTerminal = dynamic(() => import("../src/components/workspace/LiveTerminal"), { ssr: false });
const ResearchWorkspace = dynamic(() => import("../src/components/workspace/ResearchWorkspace"), { ssr: false });

import MTFRegimeMatrix from "@/components/mtf/MTFRegimeMatrix";
import RegimeTimeline from "../src/components/quant/RegimeTimeline";
import PrimaryDecisionLayer from "@/components/primary/PrimaryDecisionLayer";
import DecisionWorkflowStrip from "@/components/decision/DecisionWorkflowStrip";
import CapitalDeploymentPanel from "@/components/decision/CapitalDeploymentPanel";
import AssetOpportunityRanking from "@/components/decision/AssetOpportunityRanking";
import RegimeLifecyclePanel from "@/components/decision/RegimeLifecyclePanel";
import AnalyticsLayer from "@/components/analytics/AnalyticsLayer";
import { useDecision } from "@/hooks/useDecision";
import { useOpportunityRanking } from "@/hooks/useOpportunityRanking";
import type { MarketPayload } from "@/types/market";

export default function Home() {
  const market = useMarketStore((s) => s.market);
  const loading = useMarketStore((s) => s.loading);
  const error = useMarketStore((s) => s.error);
  const setMarket = useMarketStore((s) => s.setMarket);
  const setError = useMarketStore((s) => s.setError);
  const activeWorkspace = useMarketStore((s) => s.activeWorkspace);
  const activeAsset = useTimeframeStore((s) => s.activeAsset);
  const didInit = useRef(false);

  const marketSynced = marketMatchesAsset(market, activeAsset);

  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    let cancelled = false;
    const tfStore = useTimeframeStore.getState();
    const activeTF = tfStore.activeTimeframe;

    fetchMarketTimeframe(activeTF, tfStore.activeAsset, tfStore.activeRange)
      .then((data) => {
        if (cancelled) return;
        setMarket(data);
        tfStore.setTimeframeData(activeTF, data);

        const remaining = TIMEFRAMES.filter((tf) => tf !== activeTF);
        remaining.forEach((tf) => tfStore.fetchTimeframe(tf));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load market data");
      });

    return () => { cancelled = true; };
  }, [setMarket, setError]);

  if (error) {
    return (
      <main className="h-screen flex items-center justify-center" style={{ background: "#080809" }}>
        <div className="text-center max-w-lg">
          <h1 style={{ fontSize: 14, fontWeight: 700, color: "#ef4444", letterSpacing: "0.1em", marginBottom: 8 }}>
            MARKET DATA UNAVAILABLE
          </h1>
          <p style={{ fontSize: 11, color: "#6e6e7a" }}>{error}</p>
        </div>
      </main>
    );
  }

  if (loading || !market || !marketSynced) {
    return (
      <main className="h-screen flex items-center justify-center" style={{ background: "#080809" }}>
        <div className="text-center">
          <div style={{ fontSize: 13, fontWeight: 700, color: "#22c55e", letterSpacing: "0.15em" }} className="animate-pulse">
            INITIALIZING QUANT TERMINAL
          </div>
          <div style={{ fontSize: 9, color: "#6e6e7a", marginTop: 4, letterSpacing: "0.1em" }}>
            CONNECTING TO MARKET DATA...
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "#080809" }}>
      <TopBar market={market} />
      <MarketIntelligenceStrip market={market} />
      <WorkspaceNav />

      <div className="flex-1 overflow-hidden">
        {activeWorkspace === "chart" && <ChartWorkspace market={market} />}
        {activeWorkspace === "research" && <ResearchWorkspace />}
        {activeWorkspace === "risk" && <RiskCommandCenter />}
        {activeWorkspace === "market" && <MarketOverview />}
        {activeWorkspace === "execution" && <ExecutionMonitor />}
        {activeWorkspace === "portfolio" && <PortfolioAnalytics />}
        {activeWorkspace === "terminal" && <LiveTerminal />}
      </div>
    </div>
  );
}

function ChartWorkspace({ market }: { market: MarketPayload }) {
  const decision = useDecision(market);
  const ranking = useOpportunityRanking(market, decision);

  return (
    <div className="h-full overflow-auto" style={{ background: "#0a0a0c" }}>
      <MarketControlLayer decision={decision} />

      {decision && (
        <>
          <PrimaryDecisionLayer decision={decision} />
          <DecisionWorkflowStrip decision={decision} />
        </>
      )}

      <div className="grid grid-cols-12 gap-px" style={{ background: "#1c1c20" }}>
        <div className="col-span-12 xl:col-span-9 flex flex-col" style={{ background: "#080809" }}>
          <MainChart market={market} decision={decision} />
          <RegimeTimeline market={market} />
        </div>

        <div className="col-span-12 xl:col-span-3 flex flex-col gap-px" style={{ background: "#1c1c20" }}>
          {decision && (
            <>
              <CapitalDeploymentPanel capital={decision.capital} />
              <RegimeLifecyclePanel lifecycle={decision.lifecycle} />
            </>
          )}
          {ranking && <AssetOpportunityRanking ranking={ranking} />}
          <MTFRegimeMatrix />
        </div>
      </div>

      {decision && (
        <div style={{ marginTop: 1 }}>
          <AnalyticsLayer market={market} decision={decision} />
        </div>
      )}
    </div>
  );
}
