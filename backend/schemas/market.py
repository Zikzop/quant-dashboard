"""
Pydantic v2 response contract.

These models are the *single source of truth* for the API payload shape. The
top-level ``MarketPayload`` uses ``extra="forbid"`` so that any field the
pipeline starts emitting which isn't declared here trips a contract test
immediately — that is the mechanism that prevents silent schema drift between
backend and the zod-validated frontend.

The models are intentionally permissive where the data is genuinely dynamic
(correlation matrices keyed by asset, diagnostics) via ``dict``/``Any``, and
strict where the shape is fixed (market state, chart bars, transition matrix).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict


class MarketState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_regime: str
    volatility_regime: str
    trend_persistence: str
    transition_risk: str
    confidence: float
    adx: Optional[float] = None
    volatility: float
    risk_state: str
    trend_strength: str
    direction: str
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None


class RegimeTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: List[str]
    matrix: Dict[str, Dict[str, float]]
    counts: Dict[str, Dict[str, int]]
    persistence: Dict[str, float]
    expected_duration: Dict[str, Optional[float]]
    stationary_distribution: Dict[str, float]
    instability_score: float
    is_unstable: bool
    n_transitions: int
    low_confidence: bool
    current_state: Optional[str] = None


class ChartBar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time: Union[int, str]
    open: float
    high: float
    low: float
    close: float
    ema20: float
    ema50: float
    # Per-bar analytics (present only once the relevant engine has warmed up).
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    direction: Optional[str] = None
    trend_strength: Optional[str] = None
    garch_vol: Optional[float] = None
    vol_regime: Optional[str] = None
    hmm_regime: Optional[str] = None
    mean_revert_probability: Optional[float] = None
    trend_probability: Optional[float] = None
    crisis_probability: Optional[float] = None


class AssetInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    provider_symbol: str
    asset_class: str
    quote_currency: str
    session: Dict[str, Any]
    timezone: str


class MarketPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_id: str
    timeframe: str
    feature_version: str
    price: float
    trend: str
    market_state: MarketState
    volatility: float
    ema20: float
    ema50: float
    momentum: float
    regime: str
    structure_regime: str
    signal: str
    signal_score: float
    confidence: float
    bull_probability: float
    garch_vol: float
    vol_regime: str
    vol_slope: float
    hmm_regime: str
    trend_probability: float
    crisis_probability: float
    mean_revert_probability: float
    regime_transition: RegimeTransition
    chart_data: List[ChartBar]
    historical_range: str
    display_bars: int
    correlation: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
