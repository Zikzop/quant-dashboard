import { create } from "zustand";
import type {
  LiveOrder,
  SlippageStats,
  LatencyMetrics,
  BrokerHealth,
} from "@/types/market";

const defaultSlippage: SlippageStats = {
  avg_slippage_bps: 1.2,
  max_slippage_bps: 8.4,
  slippage_stddev: 2.1,
  positive_slippage_pct: 34,
  recent_slippage: [0.8, 1.4, 2.1, 0.3, -0.4, 1.7, 3.2, 0.9, 1.1, 0.6],
};

const defaultLatency: LatencyMetrics = {
  ws_latency_ms: 12,
  execution_latency_ms: 48,
  avg_round_trip_ms: 62,
  p99_latency_ms: 142,
  jitter_ms: 8,
};

const defaultBrokerHealth: BrokerHealth = {
  api_status: "CONNECTED",
  ws_status: "CONNECTED",
  reconnect_count: 0,
  last_heartbeat: Date.now(),
  uptime_pct: 99.94,
};

const sampleOrders: LiveOrder[] = [
  {
    id: "ORD-001",
    symbol: "BTC-PERP",
    side: "BUY",
    type: "LIMIT",
    quantity: 0.5,
    filled_quantity: 0.5,
    price: 67420,
    avg_fill_price: 67418.5,
    status: "FILLED",
    timestamp: Date.now() - 120000,
    slippage_bps: -0.22,
  },
  {
    id: "ORD-002",
    symbol: "ETH-PERP",
    side: "SELL",
    type: "MARKET",
    quantity: 5.0,
    filled_quantity: 3.2,
    price: 3842,
    avg_fill_price: 3840.1,
    status: "PARTIAL",
    timestamp: Date.now() - 45000,
    slippage_bps: 4.94,
  },
  {
    id: "ORD-003",
    symbol: "SOL-PERP",
    side: "BUY",
    type: "LIMIT",
    quantity: 100,
    filled_quantity: 0,
    price: 178.2,
    avg_fill_price: 0,
    status: "PENDING",
    timestamp: Date.now() - 8000,
    slippage_bps: 0,
  },
];

interface ExecutionStore {
  orders: LiveOrder[];
  slippage: SlippageStats;
  latency: LatencyMetrics;
  brokerHealth: BrokerHealth;

  setOrders: (o: LiveOrder[]) => void;
  addOrder: (o: LiveOrder) => void;
  updateOrder: (id: string, patch: Partial<LiveOrder>) => void;
  setSlippage: (s: SlippageStats) => void;
  setLatency: (l: LatencyMetrics) => void;
  setBrokerHealth: (b: BrokerHealth) => void;
}

export const useExecutionStore = create<ExecutionStore>((set) => ({
  orders: sampleOrders,
  slippage: defaultSlippage,
  latency: defaultLatency,
  brokerHealth: defaultBrokerHealth,

  setOrders: (o) => set({ orders: o }),
  addOrder: (o) => set((s) => ({ orders: [o, ...s.orders].slice(0, 100) })),
  updateOrder: (id, patch) =>
    set((s) => ({
      orders: s.orders.map((o) => (o.id === id ? { ...o, ...patch } : o)),
    })),
  setSlippage: (sl) => set({ slippage: sl }),
  setLatency: (l) => set({ latency: l }),
  setBrokerHealth: (b) => set({ brokerHealth: b }),
}));
