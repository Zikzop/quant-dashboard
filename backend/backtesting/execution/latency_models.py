"""
Latency models — time delay between order submission and execution.

In real markets, orders do not execute instantly. Price can move
adversely during the latency window. This is especially material
for momentum strategies where entry timing matters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class LatencyModel(ABC):
    @abstractmethod
    def sample_latency_ms(self, rng: np.random.Generator) -> float:
        """Return simulated latency in milliseconds (>= 0)."""


@dataclass(frozen=True)
class LogNormalLatency(LatencyModel):
    """
    Log-normal latency distribution.

    Captures the fat-tailed nature of real execution latency:
    most fills are fast, but occasional outliers are very slow.
    """

    mean_ms: float = 50.0
    std_ms: float = 20.0

    def sample_latency_ms(self, rng: np.random.Generator) -> float:
        mu = np.log(self.mean_ms**2 / np.sqrt(self.std_ms**2 + self.mean_ms**2))
        sigma = np.sqrt(np.log(1 + (self.std_ms / self.mean_ms) ** 2))
        return float(max(0.0, rng.lognormal(mu, sigma)))


@dataclass(frozen=True)
class FixedLatency(LatencyModel):
    """Deterministic latency (useful for controlled experiments)."""

    latency_ms: float = 50.0

    def sample_latency_ms(self, rng: np.random.Generator) -> float:
        return self.latency_ms


@dataclass(frozen=True)
class ZeroLatency(LatencyModel):
    """
    Zero latency — intentionally unrealistic.

    Only for debugging or measuring how much latency costs matter.
    """

    def sample_latency_ms(self, rng: np.random.Generator) -> float:
        return 0.0
