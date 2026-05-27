"""
Combinatorial purged cross-validation (CPCV).

Standard k-fold CV wastes data by only using 1/k for testing.
CPCV tests on all possible combinations of test groups, producing
many more OOS paths and a much more robust estimate of OOS performance.

Reference: Lopez de Prado, "Advances in Financial Machine Learning" (2018), Ch. 12.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CPCVConfig:
    """
    Combinatorial purged cross-validation configuration.

    n_groups : int
        Number of groups to split data into.
    n_test_groups : int
        Number of groups to use as test in each combination.
    purge_length : int
        Observations to purge at train/test boundaries.
    """

    n_groups: int = 6
    n_test_groups: int = 2
    purge_length: int = 5


@dataclass(frozen=True)
class CPCVResult:
    """CPCV results with distribution of OOS metrics."""

    n_combinations: int
    oos_sharpes: np.ndarray
    mean_oos_sharpe: float
    std_oos_sharpe: float
    median_oos_sharpe: float
    prob_positive_sharpe: float
    oos_returns: np.ndarray
    mean_oos_return: float
    deflated_sharpe_haircut: float
    warnings: tuple[str, ...]


def run_combinatorial_cv(
    returns: pd.Series,
    config: CPCVConfig | None = None,
) -> CPCVResult:
    """
    Run combinatorial purged cross-validation.

    Generates all C(n_groups, n_test_groups) combinations of test sets
    and evaluates OOS performance on each. Purges observations at
    train/test boundaries to prevent leakage.
    """
    cfg = config or CPCVConfig()
    r = returns.dropna().values
    n = len(r)

    group_size = n // cfg.n_groups
    if group_size < 30:
        raise ValueError(
            f"Group size ({group_size}) too small. Need at least 30 observations per group."
        )

    group_indices = []
    for i in range(cfg.n_groups):
        start = i * group_size
        end = start + group_size if i < cfg.n_groups - 1 else n
        group_indices.append((start, end))

    combos = list(combinations(range(cfg.n_groups), cfg.n_test_groups))
    n_combos = len(combos)
    logger.info("CPCV: %d combinations from %d groups", n_combos, cfg.n_groups)

    oos_sharpes = np.empty(n_combos)
    oos_returns = np.empty(n_combos)
    warnings: list[str] = []

    for combo_idx, test_groups in enumerate(combos):
        test_mask = np.zeros(n, dtype=bool)
        for g in test_groups:
            s, e = group_indices[g]
            test_mask[s:e] = True

        purge_mask = np.zeros(n, dtype=bool)
        for g in test_groups:
            s, e = group_indices[g]
            purge_start = max(0, s - cfg.purge_length)
            purge_end = min(n, e + cfg.purge_length)
            purge_mask[purge_start:s] = True
            purge_mask[e:purge_end] = True

        test_r = r[test_mask]

        if len(test_r) < 10:
            oos_sharpes[combo_idx] = 0.0
            oos_returns[combo_idx] = 0.0
            continue

        mu = np.mean(test_r)
        sigma = np.std(test_r, ddof=1)
        sharpe = mu / max(sigma, 1e-9) * np.sqrt(252)
        total_ret = float(np.prod(1 + test_r) - 1)

        oos_sharpes[combo_idx] = sharpe
        oos_returns[combo_idx] = total_ret

    mean_s = float(np.mean(oos_sharpes))
    std_s = float(np.std(oos_sharpes, ddof=1))
    prob_pos = float(np.mean(oos_sharpes > 0))

    haircut = 1.0 - prob_pos if prob_pos < 1.0 else 0.0

    if prob_pos < 0.5:
        warnings.append(
            f"Only {prob_pos*100:.0f}% of CPCV paths have positive Sharpe — "
            f"alpha is likely spurious"
        )
    if std_s > abs(mean_s) * 2:
        warnings.append(
            f"OOS Sharpe std ({std_s:.2f}) >> mean ({mean_s:.2f}) — "
            f"performance is highly unstable"
        )

    return CPCVResult(
        n_combinations=n_combos,
        oos_sharpes=oos_sharpes,
        mean_oos_sharpe=mean_s,
        std_oos_sharpe=std_s,
        median_oos_sharpe=float(np.median(oos_sharpes)),
        prob_positive_sharpe=prob_pos,
        oos_returns=oos_returns,
        mean_oos_return=float(np.mean(oos_returns)),
        deflated_sharpe_haircut=haircut,
        warnings=tuple(warnings),
    )
