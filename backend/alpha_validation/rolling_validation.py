"""
Rolling walk-forward validation for out-of-sample alpha assessment.

Expands legacy walk-forward with proper train/test separation:
parameters are fit on train, metrics computed on test only.
No future data crosses window boundaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS = 252.0


@dataclass(frozen=True)
class RollingValidationConfig:
    train_size: int = 252
    test_size: int = 63
    step_size: int | None = None
    min_train_obs: int = 60
    risk_free_rate: float = 0.02


@dataclass(frozen=True)
class FoldResult:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_obs: int
    test_obs: int
    train_sharpe: float
    test_sharpe: float
    test_expectancy: float
    test_hit_rate: float
    degradation: float


@dataclass(frozen=True)
class RollingValidationResult:
    folds: tuple[FoldResult, ...]
    mean_test_sharpe: float
    std_test_sharpe: float
    mean_degradation: float
    oos_consistency: float
    summary: str
    warnings: tuple[str, ...]


def run_rolling_validation(
    returns: pd.Series,
    *,
    config: RollingValidationConfig | None = None,
    fit_fn: Callable[[pd.Series], dict] | None = None,
    apply_fn: Callable[[pd.Series, dict], pd.Series] | None = None,
) -> RollingValidationResult:
    """
    Expanding/sliding walk-forward validation on a return series.

    If ``fit_fn`` and ``apply_fn`` are provided, train-fit parameters are
    applied to test windows. Otherwise validates the input return series
    directly on each OOS fold (useful for pre-computed strategy returns).

    Parameters
    ----------
    returns : pd.Series
        Indexed by timestamp. Per-period returns.
    fit_fn : optional
        ``fit_fn(train_returns) -> params dict`` using train data only.
    apply_fn : optional
        ``apply_fn(test_returns, params) -> strategy_returns`` for OOS eval.
    """
    cfg = config or RollingValidationConfig()
    step = cfg.step_size or cfg.test_size
    clean = _clean_returns(returns)
    warnings: list[str] = []

    if len(clean) < cfg.train_size + cfg.test_size:
        raise ValueError(
            f"Need at least {cfg.train_size + cfg.test_size} obs; got {len(clean)}"
        )

    folds: list[FoldResult] = []
    start = 0
    fold_id = 0

    while start + cfg.train_size + cfg.test_size <= len(clean):
        train = clean.iloc[start : start + cfg.train_size]
        test = clean.iloc[start + cfg.train_size : start + cfg.train_size + cfg.test_size]

        if fit_fn is not None and apply_fn is not None:
            params = fit_fn(train)
            test_strategy = apply_fn(test, params)
        else:
            test_strategy = test

        train_sharpe = _sharpe(train.values, cfg.risk_free_rate)
        test_sharpe = _sharpe(test_strategy.values, cfg.risk_free_rate)
        degradation = train_sharpe - test_sharpe

        folds.append(
            FoldResult(
                fold_id=fold_id,
                train_start=train.index[0],
                train_end=train.index[-1],
                test_start=test.index[0],
                test_end=test.index[-1],
                train_obs=len(train),
                test_obs=len(test_strategy),
                train_sharpe=train_sharpe,
                test_sharpe=test_sharpe,
                test_expectancy=float(test_strategy.mean()),
                test_hit_rate=float((test_strategy > 0).mean()),
                degradation=degradation,
            )
        )
        fold_id += 1
        start += step

    if not folds:
        raise ValueError("No walk-forward folds generated")

    test_sharpes = [f.test_sharpe for f in folds]
    degradations = [f.degradation for f in folds]
    mean_test = float(np.mean(test_sharpes))
    std_test = float(np.std(test_sharpes, ddof=1)) if len(test_sharpes) > 1 else 0.0
    mean_deg = float(np.mean(degradations))

    positive_folds = sum(1 for s in test_sharpes if s > 0)
    oos_consistency = positive_folds / len(folds)

    if mean_deg > 0.5:
        warnings.append(
            f"Mean IS-OOS Sharpe degradation={mean_deg:.2f} suggests overfitting."
        )
        logger.warning("Rolling validation: high IS-OOS degradation")

    if oos_consistency < 0.5:
        warnings.append(
            f"Only {positive_folds}/{len(folds)} folds have positive OOS Sharpe."
        )

    summary = (
        f"{len(folds)} folds: mean OOS Sharpe={mean_test:.3f} "
        f"(std={std_test:.3f}), consistency={oos_consistency:.0%}."
    )

    return RollingValidationResult(
        folds=tuple(folds),
        mean_test_sharpe=mean_test,
        std_test_sharpe=std_test,
        mean_degradation=mean_deg,
        oos_consistency=oos_consistency,
        summary=summary,
        warnings=tuple(warnings),
    )


def _sharpe(returns: np.ndarray, risk_free_rate: float) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    return float(excess.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _clean_returns(returns: pd.Series) -> pd.Series:
    s = pd.Series(returns).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        raise ValueError("Return series is empty")
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.RangeIndex(len(s))
    return s.sort_index()
