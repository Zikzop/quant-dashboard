"use client";

import { useEffect, useState } from "react";

import TopBar from "../src/components/quant/TopBar";
import MainChart from "../src/components/quant/MainChart";
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

  const [market, setMarket] =
    useState<any>(null);


  // =========================
  // FETCH MARKET DATA
  // =========================

  useEffect(() => {

    fetch("http://127.0.0.1:8000/market")
      .then((res) => res.json())
      .then((data) => {
        setMarket(data);
      });

  }, []);

  // =========================
  // LOADING
  // =========================

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

            <HeatmapPanel />

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