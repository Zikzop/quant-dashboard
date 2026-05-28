// ─────────────────────────────────────────────────────────────────────────────
// ENGINE CONTRACTS — shared output types for the quantitative engine layer.
//
// Engines are pure, framework-agnostic functions. They consume the backend
// MarketPayload (+ derived MTF state) and emit calibrated, uncertainty-aware
// decision primitives. The UI never recomputes — it only renders these.
// ─────────────────────────────────────────────────────────────────────────────

export type UncertaintyLevel = "LOW" | "MODERATE" | "HIGH" | "EXTREME";
export type StabilityLevel = "STABLE" | "FRAGILE" | "UNSTABLE";

export interface ConfidenceInterval {
  point: number; // calibrated point estimate (0..1)
  lower: number; // lower bound (0..1)
  upper: number; // upper bound (0..1)
  /** Effective sample size backing the estimate. */
  n: number;
}

export interface CalibratedProbability {
  /** Raw model probability before calibration (0..1). */
  raw: number;
  /** Calibrated probability after Platt + isotonic + Bayesian shrinkage. */
  calibrated: number;
  interval: ConfidenceInterval;
  /** How far calibration moved the estimate (raw - calibrated). */
  shrinkage: number;
}

// ── PROBABILITY ENGINE ───────────────────────────────────────────────────────

export interface ProbabilityState {
  /** Directional up-probability, calibrated (0..1). */
  bull: CalibratedProbability;
  bear: CalibratedProbability;
  /** Regime-state probabilities, calibrated. */
  trend: CalibratedProbability;
  meanRevert: CalibratedProbability;
  crisis: CalibratedProbability;
  /** Dispersion across the probability simplex (0..1, higher = less decisive). */
  dispersion: number;
  /** Method/coverage diagnostics surfaced in the research layer. */
  diagnostics: {
    method: "isotonic+platt+bayes" | "platt+bayes" | "bayes-only";
    sampleSize: number;
    horizonBars: number;
    brierRaw: number | null;
    brierCalibrated: number | null;
    reliability: Array<{ predicted: number; observed: number; n: number }>;
    plattA: number;
    plattB: number;
  };
}

// ── UNCERTAINTY ENGINE ───────────────────────────────────────────────────────

export interface UncertaintyState {
  level: UncertaintyLevel;
  /** Composite 0..1 score (higher = more uncertain). */
  score: number;
  /** Probabilistic dispersion (entropy-based, 0..1). */
  dispersion: number;
  /** Regime instability score (0..1) sourced from the HMM transition engine. */
  regimeInstability: number;
  /** Width of the directional confidence interval (0..1). */
  intervalWidth: number;
  /** Expected directional edge in % of price over the active horizon. */
  expectedEdgePct: number;
  /** Expected adverse excursion / drawdown in % (negative). */
  expectedDrawdownPct: number;
  /** Net confidence after uncertainty discount (0..1). */
  confidence: number;
}

// ── REGIME ENGINE ────────────────────────────────────────────────────────────

export type StructuralRegime =
  | "TRENDING"
  | "MEAN_REVERT"
  | "VOLATILE"
  | "CRISIS"
  | "RECOVERY"
  | "UNDEFINED";

export type MicroRegime =
  | "BULLISH_IMPULSE"
  | "BEARISH_IMPULSE"
  | "COMPRESSION"
  | "EXHAUSTION"
  | "NEUTRAL";

export type ExecutionBias =
  | "LONG_SCALP"
  | "SHORT_SCALP"
  | "BREAKOUT"
  | "FADE"
  | "NO_TRADE";

export interface RegimeDecomposition {
  structural: StructuralRegime;
  micro: MicroRegime;
  executionBias: ExecutionBias;
  /** Plain-language rationale lines for the analytics layer. */
  rationale: string[];
  /** 0..1 — agreement between structural read and micro read. */
  coherence: number;
}

// ── TRANSITION ENGINE ────────────────────────────────────────────────────────

export interface RegimeTransitionEdge {
  to: string;
  probability: number;
}

export interface TransitionState {
  current: string;
  /** Probability of remaining in the current regime next step. */
  persistence: number;
  /** Most likely regime transitions ranked by probability (excludes self). */
  nextRegimes: RegimeTransitionEdge[];
  mostLikelyNext: RegimeTransitionEdge | null;
  /** Expected dwell time in current regime (bars). */
  expectedDurationBars: number | null;
  /** P(leaving the current regime next step) = 1 - persistence. */
  transitionProbability: number;
  instability: number;
  stability: StabilityLevel;
  lowConfidence: boolean;
  available: boolean;
}

// ── CORRELATION ENGINE ───────────────────────────────────────────────────────

export type CorrelationRegime =
  | "DECOUPLED"
  | "NORMAL"
  | "ELEVATED"
  | "CRISIS_COUPLING";

export interface CorrelationState {
  available: boolean;
  regime: CorrelationRegime;
  /** Mean absolute pairwise correlation across the tracked basket (0..1). */
  meanAbsCorrelation: number;
  /** Mean signed correlation (−1..1). */
  meanCorrelation: number;
  /** Covariance instability score from the backend (0..1+). */
  instability: number;
  instabilityRegime: string;
  /** True when broad correlations spike toward 1 (diversification collapse). */
  crisisCoupling: boolean;
  /** Strongest pairwise correlation. */
  strongestPair: { pair: string; value: number } | null;
  shiftSensitivity: string;
  shiftMagnitude: number;
  warnings: string[];
}

// ── EXECUTION ENGINE ─────────────────────────────────────────────────────────

export type SessionName = "ASIA" | "LONDON" | "NY" | "NY_LONDON_OVERLAP" | "OFF_HOURS";
export type LiquidityQuality = "DEEP" | "NORMAL" | "THIN" | "ILLIQUID";

export interface ExecutionState {
  session: SessionName;
  sessionQuality: number; // 0..1
  openingDrive: boolean;
  liquidity: LiquidityQuality;
  /** Estimated half-spread in basis points. */
  spreadBps: number;
  /** Expected slippage in basis points for a marketable order. */
  expectedSlippageBps: number;
  /** Composite execution risk (0..1, higher = worse fills expected). */
  executionRisk: number;
  /** Volatility-adjusted stop distance in % of price. */
  volAdjustedStopPct: number;
  /** Suggested stop distance in price terms. */
  volAdjustedStopPrice: number;
  warnings: string[];
}

// ── RISK ENGINE ──────────────────────────────────────────────────────────────

export interface RiskState {
  /** Per-bar returns sample size used for estimation. */
  n: number;
  var95: number; // negative % loss
  var99: number;
  cvar95: number; // expected shortfall beyond VaR95
  cvar99: number;
  expectedShortfall: number;
  annualizedVol: number; // %
  /** Excess kurtosis of returns — fat-tail indicator. */
  tailKurtosis: number;
  /** Lower-tail skew (negative => crash-prone). */
  skew: number;
  tailRisk: "LOW" | "ELEVATED" | "FAT_TAILED" | "EXTREME";
  regimeConditionedVar95: number;
  volInstability: boolean;
  warnings: string[];
}

// ── DECISION COMPOSITION ─────────────────────────────────────────────────────

export type DirectionBias = "LONG" | "SHORT" | "NEUTRAL";
export type EntryQualityRating = "HIGH" | "ACCEPTABLE" | "LOW_EDGE" | "AVOID";

export interface DecisionState {
  structuralRegime: StructuralRegime;
  microRegime: MicroRegime;
  executionBias: ExecutionBias;
  direction: DirectionBias;
  directionLabel: string;
  alignmentState: "ALIGNED" | "PARTIAL" | "CONFLICT";
  alignmentRatio: number; // 0..1
  entryQuality: EntryQualityRating;
  entryScore: number; // 0..1
  riskState: string;
  confidence: number; // 0..1, uncertainty-discounted
  regimeStability: StabilityLevel;
  expectedEdgePct: number;
  expectedDrawdownPct: number;
  uncertaintyLevel: UncertaintyLevel;
  suppressTrade: boolean;
  headline: string[]; // priority warnings to surface at the top

  probability: ProbabilityState;
  uncertainty: UncertaintyState;
  regime: RegimeDecomposition;
  transition: TransitionState;
  correlation: CorrelationState;
  execution: ExecutionState;
  risk: RiskState;
}
