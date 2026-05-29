import { create } from "zustand";
import type {
  MarketPayload,
  MarketState,
  WorkspaceId,
} from "@/types/market";

interface MarketStore {
  market: MarketPayload | null;
  marketState: MarketState | null;
  wsStatus: "CONNECTED" | "RECONNECTING" | "DISCONNECTED";
  wsLatency: number;
  activeWorkspace: WorkspaceId;
  loading: boolean;
  error: string | null;

  setMarket: (data: MarketPayload) => void;
  setMarketState: (state: MarketState) => void;
  setWsStatus: (status: "CONNECTED" | "RECONNECTING" | "DISCONNECTED") => void;
  setWsLatency: (ms: number) => void;
  setActiveWorkspace: (ws: WorkspaceId) => void;
  setLoading: (v: boolean) => void;
  setError: (e: string | null) => void;
}

export const useMarketStore = create<MarketStore>((set) => ({
  market: null,
  marketState: null,
  wsStatus: "DISCONNECTED",
  wsLatency: 0,
  activeWorkspace: "chart",
  loading: true,
  error: null,

  setMarket: (data) =>
    set({ market: data, marketState: data.market_state ?? null, loading: false, error: null }),
  setMarketState: (state) => set({ marketState: state }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setWsLatency: (ms) => set({ wsLatency: ms }),
  setActiveWorkspace: (ws) => set({ activeWorkspace: ws }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e, loading: false }),
}));
