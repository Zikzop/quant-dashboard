// ─────────────────────────────────────────────────────────────────────────────
// CORE DOMAIN TYPES — Institutional Quant Terminal
// ─────────────────────────────────────────────────────────────────────────────

export interface MarketState {
  market_regime: string;
  volatility_regime: string;
  trend_persistence: string;
  transition_risk: string;
  confidence: number;
  adx: number;
  volatility: number;
  risk_state: string;
  trend_strength?: string;
  direction?: string;
  plus_di?: number;
  minus_di?: number;
}

export interface ChartBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  ema20: number;
  ema50: number;
  adx?: number;
  direction?: string;
  trend_strength?: string;
  hmm_regime?: string;
  trend_probability?: number;
  crisis_probability?: number;
  garch_vol?: number;
  vol_regime?: string;
}

export interface CorrelationPayload {
  assets?: string[];
  matrix_labels?: string[];
  matrix_values?: (number | null)[][];
  zscore_matrix_values?: number[][];
  beta_vs_btc?: Record<string, number>;
  covariance_instability?: {
    score?: number;
    regime?: string;
    frobenius_delta?: number;
  };
  regime_correlation_shift?: {
    current_regime?: string;
    shift_magnitude?: number;
    sensitivity?: string;
    largest_shifts?: Array<{
      pair: string;
      delta: number;
      long_correlation?: number;
      short_correlation?: number;
    }>;
  };
  heatmap_cells?: Array<{
    asset: string;
    daily_return_pct: number;
    beta_vs_btc: number;
    correlation_zscore_vs_btc: number;
  }>;
}

export interface MarketPayload {
  symbol?: string;
  price?: number;
  trend?: string;
  volatility?: number;
  signal?: string;
  signal_score?: number;
  momentum?: string;
  confidence?: number;
  regime?: string;
  chart_data: ChartBar[];
  market_state?: MarketState;
  garch_vol?: number;
  vol_regime?: string;
  vol_slope?: number;
  hmm_regime?: string;
  mean_revert_probability?: number;
  trend_probability?: number;
  crisis_probability?: number;
  bull_probability?: number;
  var_95?: number;
  expected_shortfall?: number;
  max_drawdown?: number;
  risk_regime?: string;
  correlation?: CorrelationPayload;
}

// ─────────────────────────────────────────────────────────────────────────────
// RISK TYPES
// ─────────────────────────────────────────────────────────────────────────────

export interface PortfolioRisk {
  total_exposure: number;
  long_exposure: number;
  short_exposure: number;
  net_exposure: number;
  leverage: number;
  beta_exposure: number;
  gross_exposure: number;
}

export interface DrawdownState {
  daily_drawdown: number;
  weekly_drawdown: number;
  max_drawdown: number;
  daily_high_water: number;
  weekly_high_water: number;
  underwater_duration: number;
}

export interface PropFirmLimits {
  daily_loss_limit: number;
  max_loss_limit: number;
  current_daily_loss: number;
  current_total_loss: number;
  remaining_daily_loss: number;
  remaining_max_loss: number;
  daily_proximity_pct: number;
  max_proximity_pct: number;
  stress_estimate: number;
  status: "SAFE" | "WARNING" | "DANGER" | "CRITICAL";
}

export interface KillSwitchState {
  volatility_kill: { active: boolean; triggered: boolean; threshold: number; current: number };
  drawdown_kill: { active: boolean; triggered: boolean; threshold: number; current: number };
  execution_kill: { active: boolean; triggered: boolean; anomaly_count: number };
  global_kill: boolean;
}

export interface RiskMetrics {
  var_95: number;
  var_99: number;
  cvar_95: number;
  cvar_99: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
}

export interface CorrelationRisk {
  max_correlation: number;
  correlated_pairs: Array<{ pair: string; correlation: number }>;
  concentration_score: number;
  hidden_factor_exposure: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// EXECUTION TYPES
// ─────────────────────────────────────────────────────────────────────────────

export type OrderStatus = "PENDING" | "FILLED" | "PARTIAL" | "REJECTED" | "CANCELLED";

export interface LiveOrder {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  type: "MARKET" | "LIMIT" | "STOP";
  quantity: number;
  filled_quantity: number;
  price: number;
  avg_fill_price: number;
  status: OrderStatus;
  timestamp: number;
  slippage_bps: number;
}

export interface SlippageStats {
  avg_slippage_bps: number;
  max_slippage_bps: number;
  slippage_stddev: number;
  positive_slippage_pct: number;
  recent_slippage: number[];
}

export interface LatencyMetrics {
  ws_latency_ms: number;
  execution_latency_ms: number;
  avg_round_trip_ms: number;
  p99_latency_ms: number;
  jitter_ms: number;
}

export interface BrokerHealth {
  api_status: "CONNECTED" | "DEGRADED" | "DISCONNECTED";
  ws_status: "CONNECTED" | "RECONNECTING" | "DISCONNECTED";
  reconnect_count: number;
  last_heartbeat: number;
  uptime_pct: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// ALPHA DIAGNOSTICS TYPES
// ─────────────────────────────────────────────────────────────────────────────

export interface AlphaDiagnostics {
  rolling_sharpe: number;
  rolling_sharpe_trend: "IMPROVING" | "STABLE" | "DETERIORATING";
  ic_decay: number;
  winrate_30d: number;
  winrate_7d: number;
  winrate_stability: "STABLE" | "UNSTABLE" | "DEGRADING";
  regime_performance: Record<string, number>;
  feature_drift: number;
  signal_stability: number;
  alpha_decay_rate: number;
  edge_reliability: number;
  trade_distribution: { long_pct: number; short_pct: number; avg_hold_hours: number };
  recent_pnl: number[];
}

// ─────────────────────────────────────────────────────────────────────────────
// PORTFOLIO ANALYTICS TYPES
// ─────────────────────────────────────────────────────────────────────────────

export interface PortfolioAllocation {
  by_asset: Array<{ asset: string; weight: number; pnl: number }>;
  by_strategy: Array<{ strategy: string; weight: number; pnl: number }>;
  by_vol_contribution: Array<{ source: string; vol_contribution: number }>;
}

export interface PerformanceAttribution {
  return_contributors: Array<{ source: string; contribution: number }>;
  loss_contributors: Array<{ source: string; contribution: number }>;
}

export interface RiskContribution {
  contributors: Array<{ source: string; risk_pct: number; marginal_var: number }>;
  dominant_factor: string;
}

export interface EquityCurveDiagnostics {
  smoothness: number;
  equity_volatility: number;
  underwater_periods: Array<{ start: string; end?: string; depth: number }>;
  equity_curve: Array<{ time: string; value: number }>;
}

// ─────────────────────────────────────────────────────────────────────────────
// LIVE TERMINAL TYPES
// ─────────────────────────────────────────────────────────────────────────────

export interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  leverage: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// ENTRY QUALITY TYPES
// ─────────────────────────────────────────────────────────────────────────────

export interface EntryQuality {
  entry_score: number;
  confidence_score: number;
  regime_confidence: number;
  quality_rating: "HIGH_QUALITY" | "ACCEPTABLE" | "LOW_EDGE" | "AVOID";
  regime_alignment: number;
  volatility_suitability: number;
  trend_strength_score: number;
  liquidity_score: number;
  correlation_environment: number;
  execution_conditions: number;
  risk_reward_quality: number;
  warnings: string[];
  signals_suppressed: boolean;
  suppression_reasons: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// WORKSPACE TYPE
// ─────────────────────────────────────────────────────────────────────────────

export type WorkspaceId =
  | "chart"
  | "risk"
  | "market"
  | "execution"
  | "alpha"
  | "portfolio"
  | "terminal";
