"""
Alpha registry — central catalog of documented institutional alpha models.

Unregistered alphas cannot be discovered via the registry API.
"""

from __future__ import annotations

import logging
from typing import Iterator

from alpha_engine.alpha_base import AlphaBase
from alpha_engine.alpha_metadata import AlphaFamily, AlphaMetadata

logger = logging.getLogger(__name__)


class AlphaRegistry:
    """Singleton-style registry for alpha model instances."""

    _instance: AlphaRegistry | None = None

    def __init__(self) -> None:
        self._alphas: dict[str, AlphaBase] = {}

    @classmethod
    def global_registry(cls) -> AlphaRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, alpha: AlphaBase, *, overwrite: bool = False) -> None:
        name = alpha.metadata.alpha_name
        if name in self._alphas and not overwrite:
            raise ValueError(f"Alpha already registered: {name}")
        self._alphas[name] = alpha
        logger.info("Registered alpha %s (family=%s)", name, alpha.metadata.family)

    def get(self, alpha_name: str) -> AlphaBase:
        if alpha_name not in self._alphas:
            raise KeyError(
                f"Unknown alpha: {alpha_name}. "
                f"Registered: {sorted(self._alphas.keys())}"
            )
        return self._alphas[alpha_name]

    def list_names(self) -> list[str]:
        return sorted(self._alphas.keys())

    def list_by_family(self, family: AlphaFamily) -> list[str]:
        return sorted(
            n for n, a in self._alphas.items() if a.metadata.family == family
        )

    def metadata(self, alpha_name: str) -> AlphaMetadata:
        return self.get(alpha_name).metadata

    def __iter__(self) -> Iterator[AlphaBase]:
        return iter(self._alphas.values())

    def clear(self) -> None:
        """Clear registry (testing only)."""
        self._alphas.clear()


def register_default_alphas(registry: AlphaRegistry | None = None) -> AlphaRegistry:
    """Register all built-in Phase 4 alpha models."""
    from alpha_engine.cross_sectional.relative_strength import RelativeStrengthAlpha
    from alpha_engine.inefficiency_research.persistence_analysis import PersistenceAlpha
    from alpha_engine.inefficiency_research.regime_transition_alpha import (
        RegimeTransitionAlpha,
    )
    from alpha_engine.inefficiency_research.volatility_regime_alpha import (
        VolatilityRegimeAlpha,
    )
    from alpha_engine.mean_reversion.regime_filtered_reversion import (
        RegimeFilteredReversionAlpha,
    )
    from alpha_engine.mean_reversion.volatility_reversion import VolatilityReversionAlpha
    from alpha_engine.mean_reversion.zscore_reversion import ZScoreReversionAlpha
    from alpha_engine.momentum.breakout_momentum import BreakoutMomentumAlpha
    from alpha_engine.momentum.trend_persistence import TrendPersistenceAlpha
    from alpha_engine.momentum.volatility_adjusted_momentum import (
        VolatilityAdjustedMomentumAlpha,
    )
    from alpha_engine.volatility.compression_detection import CompressionDetectionAlpha
    from alpha_engine.volatility.squeeze_breakout import SqueezeBreakoutAlpha
    from alpha_engine.volatility.volatility_expansion import VolatilityExpansionAlpha

    reg = registry or AlphaRegistry.global_registry()
    for alpha_cls in (
        TrendPersistenceAlpha,
        BreakoutMomentumAlpha,
        VolatilityAdjustedMomentumAlpha,
        ZScoreReversionAlpha,
        VolatilityReversionAlpha,
        RegimeFilteredReversionAlpha,
        VolatilityExpansionAlpha,
        CompressionDetectionAlpha,
        SqueezeBreakoutAlpha,
        RelativeStrengthAlpha,
        RegimeTransitionAlpha,
        VolatilityRegimeAlpha,
        PersistenceAlpha,
    ):
        instance = alpha_cls()
        reg.register(instance)
    return reg
