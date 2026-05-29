"""
Alpha metadata contract — every registered alpha must declare full provenance.

Anonymous or undocumented alpha generation is prohibited at the registry level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AlphaFamily = Literal[
    "momentum",
    "mean_reversion",
    "volatility",
    "cross_sectional",
    "inefficiency",
    "composite",
]

HoldingPeriod = Literal["intraday", "short", "medium", "long"]


@dataclass(frozen=True)
class AlphaMetadata:
    """
    Institutional metadata required for every alpha model.

    Parameters
    ----------
    alpha_name : str
        Unique registry identifier.
    description : str
        Economic hypothesis and mechanism.
    assumptions : tuple[str, ...]
        Statistical and market assumptions.
    failure_modes : tuple[str, ...]
        Known conditions under which alpha degrades.
    regime_dependency : tuple[str, ...]
        Regimes where alpha is expected to work or fail.
    holding_period : HoldingPeriod
        Typical horizon for signal decay.
    required_features : tuple[str, ...]
        Minimum feature columns from features tier.
    expected_behavior : str
        Directional expectation under ideal conditions.
    family : AlphaFamily
        Taxonomy for portfolio construction.
    version : str
        Semantic version for reproducibility.
  """

    alpha_name: str
    description: str
    assumptions: tuple[str, ...]
    failure_modes: tuple[str, ...]
    regime_dependency: tuple[str, ...]
    holding_period: HoldingPeriod
    required_features: tuple[str, ...]
    expected_behavior: str
    family: AlphaFamily
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.alpha_name or not self.alpha_name.strip():
            raise ValueError("alpha_name is required")
        if not self.description.strip():
            raise ValueError("description is required")
        if not self.assumptions:
            raise ValueError("assumptions must be non-empty")
        if not self.failure_modes:
            raise ValueError("failure_modes must be non-empty")
