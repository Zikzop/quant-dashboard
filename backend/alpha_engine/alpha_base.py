"""
Base alpha architecture — probabilistic outputs, causal computation, validation hooks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from alpha_engine.alpha_metadata import AlphaMetadata
from alpha_validation.alpha_decay import AlphaDecayAnalysis, analyze_alpha_decay
from alpha_validation.bootstrap_validation import (
    BootstrapValidationResult,
    run_bootstrap_validation,
)
from alpha_validation.rolling_validation import (
    RollingValidationResult,
    run_rolling_validation,
)

logger = logging.getLogger(__name__)

STATISTICAL_SAFETY = (
    "Feature importance and in-sample alpha do not imply causality or future edge.",
    "Historical alpha ≠ future alpha; regime instability can destroy backtested Sharpe.",
    "Non-stationarity and multiple testing inflate false discovery rates.",
)


@dataclass(frozen=True)
class RegimeContext:
    """Causal regime snapshot at signal timestamp."""

    trend_regime: str
    vol_regime: str
    stationarity_hint: str
    regime_confidence: float


@dataclass(frozen=True)
class ExpectedDistribution:
    """Parametric summary of expected forward return distribution (diagnostic)."""

    mean: float
    std: float
    skew_hint: float
    interpretation: str


@dataclass(frozen=True)
class AlphaOutput:
    """
    Probabilistic alpha output — NO raw BUY/SELL labels.

    alpha_score : float in [-1, 1]
        Directional conviction (negative = bearish tilt, positive = bullish tilt).
    confidence : float in [0, 1]
        Model confidence given current regime and feature quality.
    """

    alpha_score: float
    confidence: float
    regime_context: RegimeContext
    expected_distribution: ExpectedDistribution
    uncertainty_band: tuple[float, float]
    supporting_features: dict[str, float]
    timestamp: pd.Timestamp
    alpha_name: str
    metadata_version: str

    def __post_init__(self) -> None:
        if not -1.0 <= self.alpha_score <= 1.0:
            raise ValueError(f"alpha_score must be in [-1, 1], got {self.alpha_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")


@dataclass(frozen=True)
class AlphaSeriesOutput:
    """Time series of alpha outputs aligned to input index."""

    outputs: pd.DataFrame
    metadata: AlphaMetadata
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class AlphaValidationReport:
    """OOS validation bundle for an alpha-derived return stream."""

    bootstrap: BootstrapValidationResult
    rolling: RollingValidationResult
    decay: AlphaDecayAnalysis
    summary: str
    warnings: tuple[str, ...]


class AlphaBase(ABC):
    """
    Abstract base for institutional alpha models.

    Subclasses implement causal ``compute_series``; ``compute`` returns latest bar.
  """

    def __init__(self, metadata: AlphaMetadata) -> None:
        self.metadata = metadata

    @abstractmethod
    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        """Compute probabilistic alpha outputs for all valid timestamps."""

    def compute(self, df: pd.DataFrame) -> AlphaOutput:
        """Latest-bar alpha output."""
        series = self.compute_series(df)
        if series.outputs.empty:
            raise ValueError(f"No valid outputs for {self.metadata.alpha_name}")
        row = series.outputs.iloc[-1]
        return AlphaOutput(
            alpha_score=float(row["alpha_score"]),
            confidence=float(row["confidence"]),
            regime_context=RegimeContext(
                trend_regime=str(row["trend_regime"]),
                vol_regime=str(row["vol_regime"]),
                stationarity_hint=str(row["stationarity_hint"]),
                regime_confidence=float(row["regime_confidence"]),
            ),
            expected_distribution=ExpectedDistribution(
                mean=float(row["expected_mean"]),
                std=float(row["expected_std"]),
                skew_hint=float(row["skew_hint"]),
                interpretation=str(row["distribution_interpretation"]),
            ),
            uncertainty_band=(float(row["uncertainty_lower"]), float(row["uncertainty_upper"])),
            supporting_features={
                c: float(row[c])
                for c in series.outputs.columns
                if c.startswith("feat_")
            },
            timestamp=pd.Timestamp(row.name),
            alpha_name=self.metadata.alpha_name,
            metadata_version=self.metadata.version,
        )

    def validate(
        self,
        strategy_returns: pd.Series,
        *,
        train_size: int = 252,
        test_size: int = 63,
    ) -> AlphaValidationReport:
        """
        Run bootstrap, walk-forward, and decay analysis on alpha-implied returns.

        ``strategy_returns`` must be causal (e.g. lagged signal * forward return).
        """
        from alpha_validation.rolling_validation import RollingValidationConfig

        warnings = list(STATISTICAL_SAFETY)
        bootstrap = run_bootstrap_validation(strategy_returns)
        rolling = run_rolling_validation(
            strategy_returns,
            config=RollingValidationConfig(train_size=train_size, test_size=test_size),
        )
        decay = analyze_alpha_decay(strategy_returns)

        summary = (
            f"{self.metadata.alpha_name}: bootstrap={bootstrap.summary} "
            f"rolling={rolling.summary} decay={decay.decay_assessment}."
        )
        warnings.extend(bootstrap.warnings)
        warnings.extend(rolling.warnings)
        warnings.extend(decay.warnings)

        return AlphaValidationReport(
            bootstrap=bootstrap,
            rolling=rolling,
            decay=decay,
            summary=summary,
            warnings=tuple(warnings),
        )

    def _validate_input(self, df: pd.DataFrame) -> None:
        missing = set(self.metadata.required_features) - set(df.columns)
        if missing:
            raise ValueError(
                f"{self.metadata.alpha_name} missing features: {sorted(missing)}"
            )
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Alpha input requires DatetimeIndex")
        if df.empty:
            raise ValueError("Alpha input frame is empty")

    @staticmethod
    def sigmoid_score(x: float, scale: float = 1.0) -> float:
        """Map real line to (-1, 1) via tanh for bounded conviction."""
        return float(np.tanh(x / max(scale, 1e-9)))

    @staticmethod
    def clip_confidence(p: float | pd.Series) -> float | pd.Series:
        if isinstance(p, pd.Series):
            return p.clip(0.0, 1.0)
        return float(np.clip(p, 0.0, 1.0))

    @staticmethod
    def build_output_frame(
        index: pd.DatetimeIndex,
        *,
        alpha_score: pd.Series,
        confidence: pd.Series,
        trend_regime: pd.Series,
        vol_regime: pd.Series,
        stationarity_hint: pd.Series,
        regime_confidence: pd.Series,
        expected_mean: pd.Series,
        expected_std: pd.Series,
        skew_hint: pd.Series,
        distribution_interpretation: pd.Series,
        uncertainty_lower: pd.Series,
        uncertainty_upper: pd.Series,
        supporting: dict[str, pd.Series],
    ) -> pd.DataFrame:
        out = pd.DataFrame(
            {
                "alpha_score": alpha_score,
                "confidence": confidence,
                "trend_regime": trend_regime,
                "vol_regime": vol_regime,
                "stationarity_hint": stationarity_hint,
                "regime_confidence": regime_confidence,
                "expected_mean": expected_mean,
                "expected_std": expected_std,
                "skew_hint": skew_hint,
                "distribution_interpretation": distribution_interpretation,
                "uncertainty_lower": uncertainty_lower,
                "uncertainty_upper": uncertainty_upper,
            },
            index=index,
        )
        for name, series in supporting.items():
            out[f"feat_{name}"] = series
        return out.dropna(how="all")
