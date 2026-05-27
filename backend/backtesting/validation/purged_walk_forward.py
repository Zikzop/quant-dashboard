"""
Purged walk-forward validation — prevents information leakage between folds.

Standard walk-forward validation can leak information through:
1. Overlapping labels (purging fixes this)
2. Serial correlation bleeding into test set (embargo fixes this)

This implementation uses purging + embargo gaps as described in
Lopez de Prado, "Advances in Financial Machine Learning" (2018).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurgedWFConfig:
    """
    Purged walk-forward configuration.

    purge_length : int
        Number of observations to remove between train and test sets
        to prevent label leakage.
    embargo_pct : float
        Fraction of test set length to use as additional embargo gap.
    """

    train_size: int = 252
    test_size: int = 63
    purge_length: int = 5
    embargo_pct: float = 0.01
    min_train_size: int = 126


@dataclass(frozen=True)
class WalkForwardFold:
    """Single walk-forward fold result."""

    fold_idx: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_sharpe: float
    test_sharpe: float
    test_return: float
    test_volatility: float
    test_max_drawdown: float
    n_train: int
    n_test: int


@dataclass(frozen=True)
class PurgedWalkForwardResult:
    """Aggregated purged walk-forward validation result."""

    folds: tuple[WalkForwardFold, ...]
    mean_oos_sharpe: float
    std_oos_sharpe: float
    mean_oos_return: float
    mean_oos_max_dd: float
    sharpe_decay_rate: float
    oos_vs_is_ratio: float
    n_positive_folds: int
    n_total_folds: int
    warnings: tuple[str, ...]


def _compute_sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)
    if sigma < 1e-9:
        return 0.0
    return float(mu / sigma * np.sqrt(252))


def _compute_max_dd(returns: np.ndarray) -> float:
    equity = np.cumprod(1.0 + returns)
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / np.maximum(running_max, 1e-9)
    return float(np.min(dd))


def run_purged_walk_forward(
    returns: pd.Series,
    config: PurgedWFConfig | None = None,
) -> PurgedWalkForwardResult:
    """
    Execute purged walk-forward validation on a return series.

    Each fold:
    1. Define train window
    2. Purge observations near the train/test boundary
    3. Apply embargo gap
    4. Evaluate on clean test set
    """
    cfg = config or PurgedWFConfig()
    r = returns.dropna().values
    n = len(r)
    embargo = max(1, int(cfg.test_size * cfg.embargo_pct))

    folds: list[WalkForwardFold] = []
    warnings: list[str] = []
    start = 0
    fold_idx = 0

    while start + cfg.train_size + cfg.purge_length + embargo + cfg.test_size <= n:
        train_end = start + cfg.train_size
        test_start = train_end + cfg.purge_length + embargo
        test_end = test_start + cfg.test_size

        if test_end > n:
            break

        train_r = r[start:train_end]
        test_r = r[test_start:test_end]

        if len(train_r) < cfg.min_train_size:
            start += cfg.test_size
            continue

        train_sharpe = _compute_sharpe(train_r)
        test_sharpe = _compute_sharpe(test_r)
        test_return = float(np.prod(1 + test_r) - 1)
        test_vol = float(np.std(test_r, ddof=1) * np.sqrt(252)) if len(test_r) > 1 else 0.0
        test_dd = _compute_max_dd(test_r)

        folds.append(
            WalkForwardFold(
                fold_idx=fold_idx,
                train_start=start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_sharpe=train_sharpe,
                test_sharpe=test_sharpe,
                test_return=test_return,
                test_volatility=test_vol,
                test_max_drawdown=test_dd,
                n_train=len(train_r),
                n_test=len(test_r),
            )
        )
        fold_idx += 1
        start += cfg.test_size

    if not folds:
        raise ValueError("No valid walk-forward folds could be constructed")

    oos_sharpes = np.array([f.test_sharpe for f in folds])
    is_sharpes = np.array([f.train_sharpe for f in folds])
    oos_returns = np.array([f.test_return for f in folds])
    oos_dds = np.array([f.test_max_drawdown for f in folds])

    mean_oos = float(np.mean(oos_sharpes))
    mean_is = float(np.mean(is_sharpes))
    ratio = mean_oos / max(abs(mean_is), 1e-9)

    if len(oos_sharpes) > 2:
        x = np.arange(len(oos_sharpes))
        slope = float(np.polyfit(x, oos_sharpes, 1)[0])
    else:
        slope = 0.0

    if ratio < 0.5:
        warnings.append(
            f"OOS/IS Sharpe ratio is {ratio:.2f} — likely overfitting"
        )
    if mean_oos < 0:
        warnings.append(f"Mean OOS Sharpe is negative ({mean_oos:.2f})")
    if slope < -0.1:
        warnings.append(f"OOS Sharpe is decaying over time (slope={slope:.3f})")

    return PurgedWalkForwardResult(
        folds=tuple(folds),
        mean_oos_sharpe=mean_oos,
        std_oos_sharpe=float(np.std(oos_sharpes, ddof=1)),
        mean_oos_return=float(np.mean(oos_returns)),
        mean_oos_max_dd=float(np.mean(oos_dds)),
        sharpe_decay_rate=slope,
        oos_vs_is_ratio=ratio,
        n_positive_folds=int(np.sum(oos_sharpes > 0)),
        n_total_folds=len(folds),
        warnings=tuple(warnings),
    )
