"""
regime_engine.py
================
Institutional-Grade ADX-Based Market Regime Engine

Architecture Role
-----------------
Standalone, stateless quant module.  Drop it into any FastAPI route,
Celery task, or batch pipeline without modification.  All heavy lifting
is vectorised with NumPy / pandas; no external TA libraries required so
the maths is fully auditable.

Mathematical Foundation
-----------------------
Wilder's ADX is a smoothed ratio of directional movement:

    +DM_t = max(H_t - H_{t-1}, 0)  if  H_t - H_{t-1} > L_{t-1} - L_t  else 0
    -DM_t = max(L_{t-1} - L_t, 0)  if  L_{t-1} - L_t > H_t - H_{t-1}  else 0

    TR_t  = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)

Wilder's smoothing (NOT a simple EMA):
    ATR_t  = ATR_{t-1} - ATR_{t-1}/n + TR_t
    +DI_t  = 100 * Smooth(+DM) / Smooth(TR)
    -DI_t  = 100 * Smooth(-DM) / Smooth(TR)
    DX_t   = 100 * |+DI_t - -DI_t| / (+DI_t + -DI_t)
    ADX_t  = Wilder_smooth(DX, n)

The resulting ADX is bounded [0, 100] and measures TREND STRENGTH, not
direction.  Direction is encoded in the sign of (+DI - -DI).

Regime Classification (institutional thresholds — not retail defaults)
-----------------------------------------------------------------------
    ADX < 20            → CHOPPY   (mean-reversion, fading strategies)
    20 <= ADX < 25      → WEAK     (transitional, reduced position size)
    25 <= ADX < 40      → TRENDING (momentum, breakout strategies)
    40 <= ADX < 60      → STRONG   (trend-following, pyramiding)
    ADX >= 60           → EXTREME  (climax exhaustion risk, reduce size)

    +DI > -DI           → BULLISH  directional bias
    -DI > +DI           → BEARISH  directional bias

Statistical Caveats (read before using in production)
-----------------------------------------------------
1.  ADX is a LAGGING indicator — it reflects past n bars, not the future.
2.  Wilder smoothing introduces autocorrelation; consecutive ADX readings
    are NOT independent observations.
3.  ADX conflates volatility expansion with true directional persistence.
    In gap-rich or low-liquidity instruments the DM logic breaks down.
4.  The canonical period (14) was chosen for daily equities in the 1970s.
    On intraday futures (e.g. ES, NQ) or crypto, re-calibrate empirically.
5.  ADX is symmetric: it cannot distinguish a trending market that is
    about to reverse from one that will continue.
6.  Regime labels are DISCRETE; real market regimes are continuous latent
    states.  Use probability outputs (see HMM upgrade path) for any
    position-sizing logic.

Author: Ghassen Aloui
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RegimeStrength(str, Enum):
    """Ordinal trend-strength classification."""

    CHOPPY = "CHOPPY"  # ADX <  20  — no directional edge
    WEAK = "WEAK"  # ADX 20-25  — transitional
    TRENDING = "TRENDING"  # ADX 25-40  — reliable trend
    STRONG = "STRONG"  # ADX 40-60  — high-conviction trend
    EXTREME = "EXTREME"  # ADX >= 60  — climax / exhaustion risk


class RegimeDirection(str, Enum):
    """Directional bias derived from DI crossover."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"  # DI values too close to assign bias


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ADXResult:
    """
    Per-bar output of the ADX engine.

    Fields
    ------
    adx       : float — Wilder-smoothed trend strength [0, 100]
    plus_di   : float — +DI directional indicator [0, 100]
    minus_di  : float — -DI directional indicator [0, 100]
    dx        : float — raw directional index before final smoothing
    tr        : float — true range for the bar
    strength  : RegimeStrength — discretised strength label
    direction : RegimeDirection — directional bias
    di_spread : float — (+DI - -DI); positive = bullish
    regime    : str — human-readable composite label
    """

    adx: float
    plus_di: float
    minus_di: float
    dx: float
    tr: float
    strength: RegimeStrength
    direction: RegimeDirection
    di_spread: float
    regime: str


@dataclass
class RegimeEngineConfig:
    """
    All tuneable parameters in one place.

    period           : Wilder smoothing window (default 14)
    di_neutral_band  : DI values within +/-band of each other -> NEUTRAL direction
    thresholds       : ADX breakpoints for RegimeStrength classification
    min_bars         : minimum bars required before emitting a valid result
    """

    period: int = 14
    di_neutral_band: float = 1.0  # DI spread threshold for NEUTRAL
    thresholds: dict = field(
        default_factory=lambda: {
            "choppy": 20.0,
            "weak": 25.0,
            "trending": 40.0,
            "strong": 60.0,
        }
    )
    min_bars: int = 28  # 2x period to ensure smoothing has stabilised


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


class ADXRegimeEngine:
    """
    Vectorised, stateless ADX + regime classification engine.

    Usage (FastAPI)
    ---------------
        engine = ADXRegimeEngine(RegimeEngineConfig(period=14))

        @app.get("/regime/{symbol}")
        def get_regime(symbol: str):
            df = fetch_ohlcv(symbol)            # your data layer
            results = engine.compute(df)
            return results[-1]                  # latest bar

    Parameters
    ----------
    config : RegimeEngineConfig
    """

    def __init__(self, config: Optional[RegimeEngineConfig] = None) -> None:
        self.config = config or RegimeEngineConfig()
        self._validate_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, ohlcv: pd.DataFrame) -> list[ADXResult]:
        """
        Compute ADX + regime labels for a full OHLCV DataFrame.

        Parameters
        ----------
        ohlcv : pd.DataFrame
            Must contain columns: open, high, low, close (case-insensitive).
            Index is not used — positional ordering is assumed chronological.

        Returns
        -------
        list[ADXResult]
            One entry per bar.  Bars before config.min_bars are returned
            with NaN-equivalent floats and CHOPPY / NEUTRAL labels.

        Raises
        ------
        ValueError
            On missing columns or insufficient data.
        """
        df = self._normalise_columns(ohlcv)
        self._validate_data(df)

        high = df["high"].to_numpy(dtype=np.float64)
        low = df["low"].to_numpy(dtype=np.float64)
        close = df["close"].to_numpy(dtype=np.float64)

        tr, plus_dm, minus_dm = self._raw_directional_movement(high, low, close)
        atr, plus_dm_s, minus_dm_s = self._wilder_smooth(tr, plus_dm, minus_dm)

        plus_di, minus_di, dx, adx = self._directional_indices(
            atr, plus_dm_s, minus_dm_s
        )

        return self._build_results(adx, plus_di, minus_di, dx, tr)

    def compute_latest(self, ohlcv: pd.DataFrame) -> ADXResult:
        """Return only the most recent bar's regime — fast path for live tick."""
        results = self.compute(ohlcv)
        return results[-1]

    def compute_series(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Return results as a tidy DataFrame aligned with the input index.
        Useful for backtesting and signal overlays.
        """
        return self.compute_per_bar_series(ohlcv)

    def compute_per_bar_series(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Per-bar ADX / DI / regime labels aligned to the input index.

        Causal: Wilder smoothing at bar t uses only OHLCV observations
        from the start of the series through bar t (no future leakage).
        """
        results = self.compute(ohlcv)
        records = [
            {
                "adx": r.adx,
                "plus_di": r.plus_di,
                "minus_di": r.minus_di,
                "dx": r.dx,
                "tr": r.tr,
                "di_spread": r.di_spread,
                "strength": r.strength.value,
                "trend_strength": r.strength.value,
                "direction": r.direction.value,
                "regime": r.regime,
            }
            for r in results
        ]
        return pd.DataFrame(records, index=ohlcv.index)

    # ------------------------------------------------------------------
    # Mathematical core — fully vectorised
    # ------------------------------------------------------------------

    @staticmethod
    def _raw_directional_movement(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute per-bar TR, +DM, -DM (no smoothing applied here).

        Wilder's original definition:
            +DM = H_t - H_{t-1}  if that value > (L_{t-1} - L_t) and > 0 else 0
            -DM = L_{t-1} - L_t  if that value > (H_t - H_{t-1}) and > 0 else 0
            (Both cannot be non-zero simultaneously by construction.)

        Note: bar 0 is undefined (no prior close) — filled with 0.
        """
        n = len(high)
        tr = np.zeros(n)
        plus_dm = np.zeros(n)
        minus_dm = np.zeros(n)

        prev_high = high[:-1]
        prev_low = low[:-1]
        prev_close = close[:-1]

        curr_high = high[1:]
        curr_low = low[1:]

        # True Range
        hl = curr_high - curr_low
        hpc = np.abs(curr_high - prev_close)
        lpc = np.abs(curr_low - prev_close)
        tr[1:] = np.maximum(hl, np.maximum(hpc, lpc))

        # Raw directional movement
        up_move = curr_high - prev_high
        down_move = prev_low - curr_low

        plus_cond = (up_move > down_move) & (up_move > 0)
        minus_cond = (down_move > up_move) & (down_move > 0)

        plus_dm[1:] = np.where(plus_cond, up_move, 0.0)
        minus_dm[1:] = np.where(minus_cond, down_move, 0.0)

        return tr, plus_dm, minus_dm

    def _wilder_smooth(
        self,
        tr: np.ndarray,
        plus_dm: np.ndarray,
        minus_dm: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Wilder's smoothing — NOT an EMA despite superficial similarity.

        The recurrence relation:
            S_t = S_{t-1} - S_{t-1}/n + X_t

        This is equivalent to an EMA with alpha = 1/n (vs 2/(n+1) for EMA).
        The distinction matters: Wilder smooth is *slower* to react than EMA.
        Using a standard EMA here would be a mathematical error.

        Seed: first value = sum of first `period` raw values (Wilder's own
        initialisation, NOT the first raw value).
        """
        n = len(tr)
        period = self.config.period

        atr = np.zeros(n)
        plus_s = np.zeros(n)
        minus_s = np.zeros(n)

        if n < period + 1:
            return atr, plus_s, minus_s

        # Seed at index `period` (bars 1..period inclusive)
        atr[period] = np.sum(tr[1 : period + 1])
        plus_s[period] = np.sum(plus_dm[1 : period + 1])
        minus_s[period] = np.sum(minus_dm[1 : period + 1])

        # Vectorisation note: this recurrence has a data dependency on the
        # prior bar so we must iterate.  For n < 10_000 the loop is fast
        # enough; for production tick replay consider Numba JIT.
        for i in range(period + 1, n):
            atr[i] = atr[i - 1] - atr[i - 1] / period + tr[i]
            plus_s[i] = plus_s[i - 1] - plus_s[i - 1] / period + plus_dm[i]
            minus_s[i] = minus_s[i - 1] - minus_s[i - 1] / period + minus_dm[i]

        return atr, plus_s, minus_s

    def _directional_indices(
        self,
        atr: np.ndarray,
        plus_s: np.ndarray,
        minus_s: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Derive +DI, -DI, DX, and ADX from smoothed components.

        Guard against division-by-zero (zero ATR occurs on locked-limit
        or illiquid bars) by substituting NaN, then forward-filling.
        """
        period = self.config.period
        n = len(atr)

        with np.errstate(divide="ignore", invalid="ignore"):
            plus_di = np.where(atr > 0, 100.0 * plus_s / atr, np.nan)
            minus_di = np.where(atr > 0, 100.0 * minus_s / atr, np.nan)

        di_sum = plus_di + minus_di
        di_diff = np.abs(plus_di - minus_di)

        with np.errstate(divide="ignore", invalid="ignore"):
            dx = np.where(di_sum > 0, 100.0 * di_diff / di_sum, np.nan)

        # Final Wilder smooth of DX -> ADX
        adx = np.full(n, np.nan)

        # Seed: first valid ADX = mean of first `period` DX values starting
        # from where DX first becomes available (index `period`)
        seed_start = period
        seed_end = seed_start + period  # exclusive

        if seed_end > n:
            return plus_di, minus_di, dx, adx

        seed_dx = dx[seed_start:seed_end]
        if np.any(np.isnan(seed_dx)):
            return plus_di, minus_di, dx, adx

        adx[seed_end - 1] = np.mean(seed_dx)

        for i in range(seed_end, n):
            if not np.isnan(dx[i]) and not np.isnan(adx[i - 1]):
                adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

        return plus_di, minus_di, dx, adx

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------

    def _classify_strength(self, adx_val: float) -> RegimeStrength:
        t = self.config.thresholds
        if np.isnan(adx_val):
            return RegimeStrength.CHOPPY
        if adx_val < t["choppy"]:
            return RegimeStrength.CHOPPY
        if adx_val < t["weak"]:
            return RegimeStrength.WEAK
        if adx_val < t["trending"]:
            return RegimeStrength.TRENDING
        if adx_val < t["strong"]:
            return RegimeStrength.STRONG
        return RegimeStrength.EXTREME

    def _classify_direction(self, plus_di: float, minus_di: float) -> RegimeDirection:
        if np.isnan(plus_di) or np.isnan(minus_di):
            return RegimeDirection.NEUTRAL
        spread = plus_di - minus_di
        if abs(spread) < self.config.di_neutral_band:
            return RegimeDirection.NEUTRAL
        return RegimeDirection.BULLISH if spread > 0 else RegimeDirection.BEARISH

    @staticmethod
    def _composite_label(strength: RegimeStrength, direction: RegimeDirection) -> str:
        if strength == RegimeStrength.CHOPPY:
            return "CHOPPY_RANGE"
        return f"{direction.value}_{strength.value}"

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------

    def _build_results(
        self,
        adx: np.ndarray,
        plus_di: np.ndarray,
        minus_di: np.ndarray,
        dx: np.ndarray,
        tr: np.ndarray,
    ) -> list[ADXResult]:
        results: list[ADXResult] = []

        for i in range(len(adx)):
            adx_v = float(adx[i]) if not np.isnan(adx[i]) else float("nan")
            pdi_v = float(plus_di[i]) if not np.isnan(plus_di[i]) else float("nan")
            mdi_v = float(minus_di[i]) if not np.isnan(minus_di[i]) else float("nan")
            dx_v = float(dx[i]) if not np.isnan(dx[i]) else float("nan")
            tr_v = float(tr[i])

            strength = self._classify_strength(adx_v)
            direction = self._classify_direction(pdi_v, mdi_v)
            di_spread = (
                (pdi_v - mdi_v)
                if (not np.isnan(pdi_v) and not np.isnan(mdi_v))
                else float("nan")
            )
            regime = self._composite_label(strength, direction)

            results.append(
                ADXResult(
                    adx=adx_v,
                    plus_di=pdi_v,
                    minus_di=mdi_v,
                    dx=dx_v,
                    tr=tr_v,
                    strength=strength,
                    direction=direction,
                    di_spread=di_spread,
                    regime=regime,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        if self.config.period < 2:
            raise ValueError("ADX period must be >= 2.")
        thresholds = list(self.config.thresholds.values())
        if thresholds != sorted(thresholds):
            raise ValueError("Regime thresholds must be strictly ascending.")

    @staticmethod
    def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        required = {"high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"OHLCV DataFrame missing columns: {missing}")
        return df

    def _validate_data(self, df: pd.DataFrame) -> None:
        n = len(df)
        if n < self.config.min_bars:
            raise ValueError(
                f"Insufficient bars: {n} supplied, "
                f"{self.config.min_bars} required for stable ADX output."
            )
        if df[["high", "low", "close"]].isnull().any().any():
            logger.warning(
                "NaN values detected in OHLCV input — "
                "results for affected bars will be NaN."
            )


# ---------------------------------------------------------------------------
# FastAPI integration helpers
# ---------------------------------------------------------------------------


def regime_engine_factory(period: int = 14) -> ADXRegimeEngine:
    """
    Dependency-injection factory for FastAPI.

    Example
    -------
        from fastapi import Depends
        from regime_engine import ADXRegimeEngine, regime_engine_factory

        @app.get("/regime/{symbol}")
        def get_regime(
            symbol: str,
            engine: ADXRegimeEngine = Depends(regime_engine_factory),
        ):
            df = data_layer.fetch(symbol, bars=200)
            return engine.compute_latest(df)
    """
    return ADXRegimeEngine(RegimeEngineConfig(period=period))


def adx_result_to_dict(result: ADXResult) -> dict:
    """Serialise ADXResult to a JSON-safe dict for FastAPI response models."""
    return {
        "adx": round(result.adx, 4) if not np.isnan(result.adx) else None,
        "plus_di": round(result.plus_di, 4) if not np.isnan(result.plus_di) else None,
        "minus_di": (
            round(result.minus_di, 4) if not np.isnan(result.minus_di) else None
        ),
        "dx": round(result.dx, 4) if not np.isnan(result.dx) else None,
        "tr": round(result.tr, 6),
        "di_spread": (
            round(result.di_spread, 4) if not np.isnan(result.di_spread) else None
        ),
        "strength": result.strength.value,
        "direction": result.direction.value,
        "regime": result.regime,
    }


# ---------------------------------------------------------------------------
# Upgrade path documentation (inline — for team review)
# ---------------------------------------------------------------------------
#
# 1. VOLATILITY CLUSTERING (near-term upgrade)
#    ─────────────────────────────────────────
#    Problem   : ADX treats all "trending" bars equally regardless of vol.
#    Solution  : Overlay a GARCH(1,1) conditional variance model.
#                A trending regime with rising GARCH vol -> conviction trend.
#                A trending regime with falling vol -> potential exhaustion.
#    Libs      : arch (pip install arch)
#    Interface : Extend ADXResult with vol_regime: str ("expanding"|"contracting")
#
# 2. HIDDEN MARKOV MODEL REGIME SWITCHING (medium-term)
#    ───────────────────────────────────────────────────
#    Problem   : ADX labels are binary/discrete; real regimes are latent &
#                probabilistic.  A hard threshold at 25 is epistemically naive.
#    Solution  : Fit a 3-state Gaussian HMM on log-returns + realised vol.
#                States map to: low-vol mean-revert, trending, high-vol crisis.
#                Output: posterior state probabilities for each bar.
#    Libs      : hmmlearn
#    Caution   : HMM requires in-sample fitting -> risk of overfitting; use
#                walk-forward cross-validation with 252-bar training windows.
#
# 3. BAYESIAN REGIME DETECTION (medium-term)
#    ─────────────────────────────────────────
#    Problem   : ADX has no uncertainty quantification.  A reading of 24.9
#                (WEAK) and 25.1 (TRENDING) are treated very differently.
#    Solution  : Bayesian online changepoint detection (BOCPD — Adams & MacKay
#                2007).  Maintains a posterior over "time since last regime
#                change".  Emits a probability that a structural break has
#                occurred, enabling soft regime transitions.
#    Libs      : bayesian_changepoint_detection or custom NumPy implementation
#
# 4. TREND PERSISTENCE MODELS (long-term)
#    ──────────────────────────────────────
#    Problem   : ADX tells you a trend exists; it doesn't say how long it will
#                last.  Position sizing needs a survival model.
#    Solution  : Fit a discrete-time hazard model (Cox PH or parametric
#                Weibull) on regime durations.  Inputs: ADX level, DI spread,
#                sector beta, macro regime.  Output: P(regime continues k bars).
#    Libs      : lifelines
#
# 5. KNOWN WEAKNESSES OF THIS MODULE
#    ──────────────────────────────────
#    a) Wilder smoothing lag: ADX at bar t reflects information up to ~2n bars
#       ago.  For n=14 that is ~28 bars of true latency.
#    b) Parameter sensitivity: the 14-period default is NOT universal.
#       Calibrate with Sharpe-optimised grid search per instrument / timeframe.
#    c) Gap risk: overnight / weekend gaps inflate TR without genuine
#       directional movement; consider a gap-adjusted TR variant.
#    d) Microstructure noise: on sub-minute bars the DM signal is dominated
#       by bid-ask bounce; minimum recommended granularity is 5-minute bars.
#    e) Non-stationarity: ADX thresholds calibrated on historical data may
#       not hold in structurally different future regimes (e.g. post-QE).
