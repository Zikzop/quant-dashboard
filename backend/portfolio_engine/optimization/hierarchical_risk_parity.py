"""
Hierarchical Risk Parity (HRP) — clustering-based portfolio construction.

Implements the de Prado (2016) HRP algorithm:
1. Compute distance matrix from correlation.
2. Hierarchical clustering (single linkage by default).
3. Quasi-diagonalization of the covariance matrix.
4. Top-down recursive bisection for weight allocation.

Statistical advantages over Markowitz:
- Does NOT invert the covariance matrix → stable with singular/near-singular Σ.
- Exploits correlation structure via clustering → natural diversification.
- More robust to estimation error in covariance.
- Works well in high-dimensional settings (many assets, short history).

Known limitations:
- Does not incorporate expected returns (purely risk-based).
- The clustering linkage method and distance metric affect results.
- Not a "true" optimization — no objective function is minimized.
- Sensitive to the choice of distance metric for clustering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

from portfolio_engine.portfolio_base import PortfolioConstraints, PortfolioWeights

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HRPConfig:
    linkage_method: str = "single"
    distance_metric: str = "correlation"
    max_weight: float = 0.25
    min_weight: float = 0.0
    max_leverage: float = 1.0


@dataclass(frozen=True)
class HRPResult:
    weights: PortfolioWeights
    risk_contributions: dict[str, float]
    portfolio_volatility: float
    cluster_order: list[str]
    dendrogram_distances: list[float]
    warnings: list[str] = field(default_factory=list)


class HierarchicalRiskParityOptimizer:
    """
    HRP portfolio construction using correlation-based clustering.

    Avoids covariance matrix inversion entirely, making it suitable for
    large or ill-conditioned asset universes.
    """

    def __init__(
        self,
        config: HRPConfig | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> None:
        self._config = config or HRPConfig()
        self._constraints = constraints or PortfolioConstraints(long_only=True)

    def optimize(
        self,
        covariance_matrix: pd.DataFrame,
        correlation_matrix: pd.DataFrame | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> HRPResult:
        cfg = self._config
        warnings: list[str] = []

        symbols = list(covariance_matrix.columns)
        n = len(symbols)
        cov = covariance_matrix.values.astype(float)

        if correlation_matrix is not None:
            corr = correlation_matrix.loc[symbols, symbols].values.astype(float)
        else:
            vols = np.sqrt(np.diag(cov))
            vol_outer = np.outer(vols, vols)
            vol_outer = np.where(vol_outer > 1e-12, vol_outer, 1.0)
            corr = cov / vol_outer
            np.fill_diagonal(corr, 1.0)

        corr = np.clip(corr, -1.0, 1.0)
        np.fill_diagonal(corr, 1.0)

        dist = self._correlation_distance(corr)

        condensed = squareform(dist, checks=False)
        condensed = np.maximum(condensed, 0.0)

        try:
            link = linkage(condensed, method=cfg.linkage_method)
        except Exception as e:
            warnings.append(f"Linkage failed ({e}), falling back to inverse-vol weights")
            return self._fallback_inverse_vol(cov, symbols, timestamp, warnings)

        sort_ix = list(leaves_list(link).astype(int))
        sorted_symbols = [symbols[i] for i in sort_ix]

        cov_sorted = cov[np.ix_(sort_ix, sort_ix)]

        w = self._recursive_bisection(cov_sorted, list(range(n)))

        w = np.maximum(w, cfg.min_weight)
        w = np.minimum(w, cfg.max_weight)
        w_sum = w.sum()
        if w_sum > 1e-12:
            w /= w_sum

        gross = float(np.sum(np.abs(w)))
        if gross > cfg.max_leverage:
            w *= cfg.max_leverage / gross

        weight_map = {}
        for i, idx in enumerate(sort_ix):
            weight_map[symbols[idx]] = float(w[i])

        sigma_w = cov @ np.array([weight_map[s] for s in symbols])
        port_var = float(
            np.array([weight_map[s] for s in symbols]) @ sigma_w
        )
        port_vol = float(np.sqrt(max(port_var, 0.0)))

        w_arr = np.array([weight_map[s] for s in symbols])
        if port_vol > 1e-12:
            mc = sigma_w / port_vol
            rc = w_arr * mc
            rc_sum = rc.sum()
            rc_frac = rc / rc_sum if abs(rc_sum) > 1e-12 else np.ones(n) / n
        else:
            rc_frac = np.ones(n) / n

        dendro_dists = [float(link[i, 2]) for i in range(len(link))]

        ts = timestamp or pd.Timestamp.now(tz="UTC")
        weights = PortfolioWeights(
            weights=weight_map,
            timestamp=ts,
            method="hierarchical_risk_parity",
        )

        return HRPResult(
            weights=weights,
            risk_contributions={symbols[i]: float(rc_frac[i]) for i in range(n)},
            portfolio_volatility=port_vol,
            cluster_order=sorted_symbols,
            dendrogram_distances=dendro_dists,
            warnings=warnings,
        )

    @staticmethod
    def _correlation_distance(corr: np.ndarray) -> np.ndarray:
        """Convert correlation to distance: d = sqrt(0.5 * (1 - corr))"""
        dist = np.sqrt(np.clip(0.5 * (1 - corr), 0.0, 1.0))
        np.fill_diagonal(dist, 0.0)
        return dist

    @staticmethod
    def _recursive_bisection(
        cov: np.ndarray, indices: list[int]
    ) -> np.ndarray:
        """
        Top-down recursive bisection: allocate risk inversely proportional
        to cluster variance at each split.
        """
        n = len(indices)
        w = np.ones(n)

        clusters = [indices]

        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]

                var_left = _cluster_variance(cov, left)
                var_right = _cluster_variance(cov, right)

                total_var = var_left + var_right
                if total_var < 1e-12:
                    alpha = 0.5
                else:
                    alpha = 1.0 - var_left / total_var

                for i in left:
                    w[i] *= alpha
                for i in right:
                    w[i] *= (1.0 - alpha)

                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)

            clusters = new_clusters

        return w

    def _fallback_inverse_vol(
        self,
        cov: np.ndarray,
        symbols: list[str],
        timestamp: pd.Timestamp | None,
        warnings: list[str],
    ) -> HRPResult:
        vols = np.sqrt(np.diag(cov))
        vols = np.maximum(vols, 1e-8)
        inv_vol = 1.0 / vols
        w = inv_vol / inv_vol.sum()

        ts = timestamp or pd.Timestamp.now(tz="UTC")
        weights = PortfolioWeights(
            weights={symbols[i]: float(w[i]) for i in range(len(symbols))},
            timestamp=ts,
            method="hrp_fallback_inverse_vol",
        )
        return HRPResult(
            weights=weights,
            risk_contributions={s: 1.0 / len(symbols) for s in symbols},
            portfolio_volatility=0.0,
            cluster_order=symbols,
            dendrogram_distances=[],
            warnings=warnings,
        )


def _cluster_variance(cov: np.ndarray, indices: list[int]) -> float:
    """Inverse-variance portfolio variance for a cluster subset."""
    sub_cov = cov[np.ix_(indices, indices)]
    diag = np.diag(sub_cov)
    diag = np.maximum(diag, 1e-10)
    inv_diag = 1.0 / diag
    w = inv_diag / inv_diag.sum()
    return float(w @ sub_cov @ w)
