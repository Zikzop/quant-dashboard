"""Data-quality validation + statistical validation framework."""

from validation.framework import (
    ValidationFramework,
    ValidationReport,
    ema_trend_signal,
    volatility_regime,
)
from validation.ohlcv_validator import OHLCVValidationReport, OHLCVValidator
from validation.walk_forward import Fold, WalkForwardSplitter

__all__ = [
    "OHLCVValidator",
    "OHLCVValidationReport",
    "ValidationFramework",
    "ValidationReport",
    "ema_trend_signal",
    "volatility_regime",
    "WalkForwardSplitter",
    "Fold",
]
