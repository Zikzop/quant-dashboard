"""
Rolling correlation — tracks pairwise and portfolio-level correlations over time.

Correlations are not constants. They evolve with market regimes, policy
shifts, and structural changes. Monitoring rolling correlations reveals:
- When formerly uncorrelated assets start moving together
- When diversification is real vs. illusory
- When the portfolio's effective bet count is shrinking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import CorrelationConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrelationSnapshot:
    """Point-in-time correlation metrics."""

    mean_pairwise_correlation: float
    median_pairwise_correlation: float
    max_pairwise_correlation: float
    max_corr_pair: tuple[str, str]
    min_pairwise_correlation: float
    correlation_dispersion: float
    n_pairs: int
    n_high_corr_pairs: int
    eigenvalue_concentration: float


class RollingCorrelationEngine:
    """
    Tracks rolling pairwise correlations and aggregate metrics.

    Uses both simple rolling and EWMA correlations. The EWMA version
    responds faster to regime shifts; the simple version is more stable.
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self._config = config or CorrelationConfig()
        self._history: list[tuple[pd.Timestamp, CorrelationSnapshot]] = []

    def compute(
        self,
        returns: pd.DataFrame,
        timestamp: pd.Timestamp | None = None,
    ) -> CorrelationSnapshot:
        """
        Compute correlation snapshot from multi-asset return DataFrame.

        Parameters
        ----------
        returns : DataFrame with columns = asset names, rows = dates
        """
        window = self._config.rolling_window_days
        if len(returns) < window:
            recent = returns
        else:
            recent = returns.iloc[-window:]

        if recent.shape[1] < 2:
            snap = CorrelationSnapshot(
                mean_pairwise_correlation=0.0,
                median_pairwise_correlation=0.0,
                max_pairwise_correlation=0.0,
                max_corr_pair=("", ""),
                min_pairwise_correlation=0.0,
                correlation_dispersion=0.0,
                n_pairs=0,
                n_high_corr_pairs=0,
                eigenvalue_concentration=1.0,
            )
            if timestamp:
                self._history.append((timestamp, snap))
            return snap

        corr_matrix = recent.corr()
        n = corr_matrix.shape[0]
        cols = corr_matrix.columns.tolist()

        pairs = []
        pair_names = []
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append(corr_matrix.iloc[i, j])
                pair_names.append((cols[i], cols[j]))

        if not pairs:
            snap = CorrelationSnapshot(
                mean_pairwise_correlation=0.0,
                median_pairwise_correlation=0.0,
                max_pairwise_correlation=0.0,
                max_corr_pair=("", ""),
                min_pairwise_correlation=0.0,
                correlation_dispersion=0.0,
                n_pairs=0,
                n_high_corr_pairs=0,
                eigenvalue_concentration=1.0,
            )
            if timestamp:
                self._history.append((timestamp, snap))
            return snap

        pairs_arr = np.array(pairs)
        max_idx = int(np.argmax(pairs_arr))
        n_high = int(np.sum(np.abs(pairs_arr) > 0.7))

        cov = recent.cov().values
        try:
            eigenvalues = np.linalg.eigvalsh(cov)
            eigenvalues = eigenvalues[eigenvalues > 0]
            eigen_conc = float(eigenvalues[-1] / np.sum(eigenvalues)) if len(eigenvalues) > 0 else 1.0
        except np.linalg.LinAlgError:
            eigen_conc = 1.0

        snap = CorrelationSnapshot(
            mean_pairwise_correlation=float(np.mean(pairs_arr)),
            median_pairwise_correlation=float(np.median(pairs_arr)),
            max_pairwise_correlation=float(pairs_arr[max_idx]),
            max_corr_pair=pair_names[max_idx],
            min_pairwise_correlation=float(np.min(pairs_arr)),
            correlation_dispersion=float(np.std(pairs_arr)),
            n_pairs=len(pairs),
            n_high_corr_pairs=n_high,
            eigenvalue_concentration=eigen_conc,
        )

        if timestamp:
            self._history.append((timestamp, snap))
        return snap

    def history_dataframe(self) -> pd.DataFrame:
        if not self._history:
            return pd.DataFrame()
        records = []
        for ts, snap in self._history:
            records.append({
                "timestamp": ts,
                "mean_corr": snap.mean_pairwise_correlation,
                "max_corr": snap.max_pairwise_correlation,
                "n_high_pairs": snap.n_high_corr_pairs,
                "eigen_conc": snap.eigenvalue_concentration,
            })
        return pd.DataFrame(records).set_index("timestamp")
