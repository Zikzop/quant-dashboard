"""
Leverage monitoring — tracks gross and net leverage against limits.

Leverage is the amplifier of both returns and losses. Institutional risk
systems monitor leverage continuously, not just at rebalance time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from risk_engine.risk_config import ExposureConfig
from risk_engine.exposure.gross_net_exposure import ExposureSnapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeverageStatus:
    """Point-in-time leverage assessment."""

    gross_leverage: float
    net_leverage: float
    gross_limit: float
    net_limit: float
    gross_utilization: float
    net_utilization: float
    gross_breach: bool
    net_breach: bool
    headroom_gross: float
    headroom_net: float


class LeverageMonitor:
    """Evaluates leverage against configured limits."""

    def __init__(self, config: ExposureConfig | None = None) -> None:
        self._config = config or ExposureConfig()

    def check(self, exposure: ExposureSnapshot) -> LeverageStatus:
        gross_util = (
            exposure.gross_leverage / self._config.max_gross_leverage
            if self._config.max_gross_leverage > 0 else 0.0
        )
        net_util = (
            abs(exposure.net_leverage) / self._config.max_net_exposure_ratio
            if self._config.max_net_exposure_ratio > 0 else 0.0
        )

        return LeverageStatus(
            gross_leverage=exposure.gross_leverage,
            net_leverage=exposure.net_leverage,
            gross_limit=self._config.max_gross_leverage,
            net_limit=self._config.max_net_exposure_ratio,
            gross_utilization=gross_util,
            net_utilization=net_util,
            gross_breach=exposure.gross_leverage > self._config.max_gross_leverage,
            net_breach=abs(exposure.net_leverage) > self._config.max_net_exposure_ratio,
            headroom_gross=max(0.0, self._config.max_gross_leverage - exposure.gross_leverage),
            headroom_net=max(0.0, self._config.max_net_exposure_ratio - abs(exposure.net_leverage)),
        )
