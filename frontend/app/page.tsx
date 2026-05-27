"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

import TopBar from "../src/components/quant/TopBar";
import WorkspaceNav from "../src/components/workspace/WorkspaceNav";
import MarketIntelligenceStrip from "@/visualization/intelligence/MarketIntelligenceStrip";
import TimeframeSelector from "@/components/mtf/TimeframeSelector";
import { useMarketStore } from "@/state/stores/useMarketStore";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

const MainChart = dynamic(() => import("../src/components/quant/MainChart"), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center" style={{ background: "#080809", color: "#555560", fontSize: 11, letterSpacing: "0.1em" }}>
      LOADING CHART ENGINE...
    </div>
  ),
});

const RiskCommandCenter = dynamic(() => import("../src/components/workspace/RiskCommandCenter"), { ssr: false });
const MarketOverview = dynamic(() => import("../src/components/workspace/MarketOverview"), { ssr: false });
const ExecutionMonitor = dynamic(() => import("../src/components/workspace/ExecutionMonitor"), { ssr: false });
const AlphaDiagnostics = dynamic(() => import("../src/components/workspace/AlphaDiagnostics"), { ssr: false });
const PortfolioAnalytics = dynamic(() => import("../src/components/workspace/PortfolioAnalytics"), { ssr: false });
const LiveTerminal = dynamic(() => import("../src/components/workspace/LiveTerminal"), { ssr: false });

import MTFRegimeMatrix from "@/components/mtf/MTFRegimeMatrix";
import HistoricalRegimePanel from "@/components/mtf/HistoricalRegimePanel";
import ProbabilityPanel from "../src/components/quant/ProbabilityPanel";
import RiskPanel from "../src/components/quant/RiskPanel";
import RegimePanel from "../src/components/quant/RegimePanel";
import RegimeTimeline from "../src/components/quant/RegimeTimeline";
import VolatilityPanel from "../src/components/quant/VolatilityPanel";
import StructurePanel from "../src/components/quant/StructurePanel";
import HeatmapPanel from "../src/components/quant/HeatmapPanel";

export default function Home() {
  const market = useMarketStore((s) => s.market);
  const loading = useMarketStore((s) => s.loading);
  const error = useMarketStore((s) => s.error);
  const setMarket = useMarketStore((s) => s.setMarket);
  const setError = useMarketStore((s) => s.setError);
  const activeWorkspace = useMarketStore((s) => s.activeWorkspace);
  const updateMTF = useTimeframeStore((s) => s.updateFromMarket);

  useEffect(() => {
    let cancelled = false;

    fetch("http://127.0.0.1:8000/market")
      .then((res) => {
        if (!res.ok) throw new Error(`Market API returned ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setMarket(data);
          updateMTF(data);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load market data");
      });

    return () => { cancelled = true; };
  }, [setMarket, setError, updateMTF]);

  if (error) {
    return (
      <main className="h-screen flex items-center justify-center" style={{ background: "#080809" }}>
        <div className="text-center max-w-lg">
          <h1 style={{ fontSize: 14, fontWeight: 700, color: "#ef4444", letterSpacing: "0.1em", marginBottom: 8 }}>
            MARKET DATA UNAVAILABLE
          </h1>
          <p style={{ fontSize: 11, color: "#555560" }}>{error}</p>
        </div>
      </main>
    );
  }

  if (loading || !market) {
    return (
      <main className="h-screen flex items-center justify-center" style={{ background: "#080809" }}>
        <div className="text-center">
          <div style={{ fontSize: 13, fontWeight: 700, color: "#22c55e", letterSpacing: "0.15em" }} className="animate-pulse">
            INITIALIZING QUANT TERMINAL
          </div>
          <div style={{ fontSize: 9, color: "#555560", marginTop: 4, letterSpacing: "0.1em" }}>
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
        {activeWorkspace === "risk" && <RiskCommandCenter />}
        {activeWorkspace === "market" && <MarketOverview />}
        {activeWorkspace === "execution" && <ExecutionMonitor />}
        {activeWorkspace === "alpha" && <AlphaDiagnostics />}
        {activeWorkspace === "portfolio" && <PortfolioAnalytics />}
        {activeWorkspace === "terminal" && <LiveTerminal />}
      </div>
    </div>
  );
}

function ChartWorkspace({ market }: { market: any }) {
  return (
    <div className="h-full overflow-auto" style={{ background: "#0a0a0c" }}>
      <TimeframeSelector />
      <div className="grid grid-cols-12 gap-px" style={{ background: "#1c1c20" }}>
        <div className="col-span-12 xl:col-span-9" style={{ background: "#080809" }}>
          <MainChart market={market} />
          <div className="grid grid-cols-12 gap-px" style={{ background: "#1c1c20" }}>
            <div className="col-span-12" style={{ background: "#080809" }}>
              <RegimeTimeline market={market} />
            </div>
            <div className="col-span-6" style={{ background: "#080809" }}>
              <VolatilityPanel market={market} />
            </div>
            <div className="col-span-6" style={{ background: "#080809" }}>
              <StructurePanel market={market} />
            </div>
            <div className="col-span-12" style={{ background: "#080809" }}>
              <HeatmapPanel market={market} />
            </div>
          </div>
        </div>
        <div className="col-span-12 xl:col-span-3 flex flex-col gap-px" style={{ background: "#1c1c20" }}>
          <div style={{ background: "#080809" }}>
            <MTFRegimeMatrix />
          </div>
          <div style={{ background: "#080809" }}>
            <HistoricalRegimePanel />
          </div>
          <div style={{ background: "#080809" }}>
            <ProbabilityPanel market={market} />
          </div>
          <div style={{ background: "#080809" }}>
            <RiskPanel market={market} />
          </div>
          <div style={{ background: "#080809" }}>
            <RegimePanel market={market} />
          </div>
        </div>
      </div>
    </div>
  );
}
