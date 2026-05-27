"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import TopBar from "../src/components/quant/TopBar";

const MainChart = dynamic(
  () => import("../src/components/quant/MainChart"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[680px] w-full bg-black flex items-center justify-center text-zinc-500 text-sm">
        Loading chart...
      </div>
    ),
  }
);
import ProbabilityPanel from "../src/components/quant/ProbabilityPanel";
import RiskPanel from "../src/components/quant/RiskPanel";
import RegimePanel from "../src/components/quant/RegimePanel";
import MarketFeed from "../src/components/quant/MarketFeed";

import VolatilityPanel from "../src/components/quant/VolatilityPanel";
import StructurePanel from "../src/components/quant/StructurePanel";
import HeatmapPanel from "../src/components/quant/HeatmapPanel";
import RegimeTimeline from "../src/components/quant/RegimeTimeline";

import MarketIntelligenceStrip from "@/visualization/intelligence/MarketIntelligenceStrip";



export default function Home() {

  const [market, setMarket] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("http://127.0.0.1:8000/market")
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Market API returned ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setMarket(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load market data"
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <main className="min-h-screen bg-black text-white flex items-center justify-center p-8">
        <div className="text-center max-w-lg">
          <h1 className="text-2xl font-bold text-red-400 mb-3">
            Market data unavailable
          </h1>
          <p className="text-zinc-400 text-sm">{error}</p>
        </div>
      </main>
    );
  }

  if (!market) {
    return (
      <main className="min-h-screen bg-black text-white flex items-center justify-center">
        <h1 className="text-4xl font-bold text-green-400 animate-pulse">
          Loading Quant Terminal...
        </h1>
      </main>
    );
  }

  // =========================
  // UI
  // =========================

  return (

    <div className="space-y-4">

      <main className="min-h-screen bg-black text-white flex flex-col">

        <TopBar market={market} />

        <div className="sticky top-0 z-50">

          <MarketIntelligenceStrip
            market={market}
          />

        </div>

        <div className="grid grid-cols-12 gap-4 p-4">

          {/* MAIN AREA */}

          <div className="col-span-12 xl:col-span-9 flex flex-col gap-4">

            <MainChart market={market} />

            <RegimeTimeline market={market} />

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">

              <VolatilityPanel market={market} />

              <StructurePanel market={market} />

            </div>

            <HeatmapPanel market={market} />

          </div>

          {/* RIGHT PANEL */}

          <div className="col-span-12 xl:col-span-3 flex flex-col gap-4">

            <ProbabilityPanel market={market} />

            <RiskPanel market={market} />

            <RegimePanel market={market} />

          </div>

        </div>

        <div className="p-4">

          <MarketFeed />

        </div>

      </main>

    </div>
  );
}