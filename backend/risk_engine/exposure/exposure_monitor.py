"""
Exposure monitor — aggregates all exposure signals and detects breaches.

This is the top-level exposure component that coordinates gross/net exposure,
leverage, concentration, and factor exposure into a unified view. It checks
thresholds and produces breach signals for the governance layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from risk_engine.risk_config import ExposureConfig, RiskRegime
from risk_engine.exposure.gross_net_exposure import GrossNetExposureEngine, ExposureSnapshot
from risk_engine.exposure.leverage_monitor import LeverageMonitor, LeverageStatus
from risk_engine.exposure.concentration_monitor import ConcentrationMonitor, ConcentrationSnapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureAssessment:
    """Unified exposure risk assessment."""

    timestamp: pd.Timestamp
    exposure: ExposureSnapshot
    leverage_status: LeverageStatus
    concentration: ConcentrationSnapshot
    breaches: tuple[str, ...]
    risk_regime: RiskRegime
    requires_action: bool


class ExposureMonitor:
    """
    Aggregates gross/net exposure, leverage, and concentration monitoring.

    Produces a unified ExposureAssessment that feeds into the governance layer.
    """

    def __init__(self, config: ExposureConfig | None = None) -> None:
        self._config = config or ExposureConfig()
        self._gross_net = GrossNetExposureEngine()
        self._leverage = LeverageMonitor(config=self._config)
        self._concentration = ConcentrationMonitor(config=self._config)

    def assess(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        nav: float,
        timestamp: pd.Timestamp,
        volatilities: dict[str, float] | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> ExposureAssessment:
        exposure = self._gross_net.compute(
            positions=positions,
            prices=prices,
            nav=nav,
            timestamp=timestamp,
            volatilities=volatilities,
        )
        leverage_status = self._leverage.check(exposure)
        concentration = self._concentration.compute(
            positions=positions,
            prices=prices,
            nav=nav,
            sector_map=sector_map,
        )

        breaches: list[str] = []
        if leverage_status.gross_breach:
            breaches.append(
                f"Gross leverage {exposure.gross_leverage:.2f} exceeds "
                f"limit {self._config.max_gross_leverage:.2f}"
            )
        if leverage_status.net_breach:
            breaches.append(
                f"Net exposure ratio {abs(exposure.net_leverage):.2f} exceeds "
                f"limit {self._config.max_net_exposure_ratio:.2f}"
            )
        if concentration.max_single_name > self._config.max_single_name_weight:
            breaches.append(
                f"Single-name concentration {concentration.max_single_name:.2f} "
                f"exceeds limit {self._config.max_single_name_weight:.2f}"
            )
        if concentration.hhi > self._config.concentration_hhi_critical:
            breaches.append(
                f"HHI concentration {concentration.hhi:.3f} exceeds "
                f"critical threshold {self._config.concentration_hhi_critical:.3f}"
            )

        regime = self._classify_regime(exposure, concentration, len(breaches))

        return ExposureAssessment(
            timestamp=timestamp,
            exposure=exposure,
            leverage_status=leverage_status,
            concentration=concentration,
            breaches=tuple(breaches),
            risk_regime=regime,
            requires_action=len(breaches) > 0,
        )

    def _classify_regime(
        self,
        exposure: ExposureSnapshot,
        concentration: ConcentrationSnapshot,
        n_breaches: int,
    ) -> RiskRegime:
        if n_breaches >= 2:
            return RiskRegime.CRISIS
        if n_breaches == 1:
            return RiskRegime.STRESSED
        if (
            exposure.gross_leverage > self._config.max_gross_leverage * 0.85
            or concentration.hhi > self._config.concentration_hhi_warning
        ):
            return RiskRegime.ELEVATED
        return RiskRegime.NORMAL
