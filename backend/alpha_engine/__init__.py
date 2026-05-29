"""
Institutional alpha engine — probabilistic, regime-aware research alpha framework.
"""

from alpha_engine.alpha_base import (
    STATISTICAL_SAFETY,
    AlphaBase,
    AlphaOutput,
    AlphaSeriesOutput,
    AlphaValidationReport,
)
from alpha_engine.alpha_metadata import AlphaMetadata, AlphaFamily
from alpha_engine.alpha_registry import AlphaRegistry, register_default_alphas
from alpha_engine.signal_combination.confidence_aggregation import aggregate_confidence
from alpha_engine.signal_combination.probabilistic_combiner import ProbabilisticCombiner

__all__ = [
    "STATISTICAL_SAFETY",
    "AlphaBase",
    "AlphaFamily",
    "AlphaMetadata",
    "AlphaOutput",
    "AlphaRegistry",
    "AlphaSeriesOutput",
    "AlphaValidationReport",
    "ProbabilisticCombiner",
    "aggregate_confidence",
    "register_default_alphas",
]
