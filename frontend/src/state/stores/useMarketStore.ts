import { create } from "zustand"

import { MarketState } from "@/types/market"

interface MarketStore {
  marketState: MarketState | null

  setMarketState: (state: MarketState) => void
}

export const useMarketStore = create<MarketStore>((set) => ({
  marketState: null,

  setMarketState: (state) =>
    set({
      marketState: state
    })
}))