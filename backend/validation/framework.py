"""
Validation framework: walk-forward, out-of-sample evaluation, report.

A ``signal engine`` under test is any causal function

    signal_fn(train_df, test_df) -> positions for test_df  (values in {-1,0,1})

The framework never lets the engine see future data: positions for a fold are
produced from that fold's train window only, then scored against the *next*-bar
forward return on the held-out test window. Aggregating across non-overlapping
test windows yields a true OOS track record, from which it computes the metric
suite (hit rate, avg return, drawdown, Sharpe, PSR, deflated Sharpe placeholder,
regime persistence, transition stability) and emits a per-engine report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from regime.transition_matrix import CANONICAL_REGIMES, build_transition_model
from validation.metrics import (
    OOSMetrics,
    avg_return,
    deflated_sharpe_ratio,
    hit_rate,
    max_drawdown,
    probabilistic_sharpe_ratio,
    regime_persistence,
    sharpe_ratio,
    transition_stability,
)
from validation.walk_forward import Fold, WalkForwardSplitter

SignalFn = Callable[[pd.DataFrame, pd.DataFrame], pd.Series]
RegimeFn = Callable[[pd.DataFrame, pd.DataFrame], pd.Series]


def _forward_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().shift(-1)


def ema_trend_signal(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """Default signal engine under test: causal EMA20/50 stack direction.

    EMAs are computed on the train+test prefix so each test bar uses only
    information available up to that bar (no leakage from the future).
    """
    combined = pd.concat([train_df, test_df])["Close"].astype(float)
    ema20 = combined.ewm(span=20).mean()
    ema50 = combined.ewm(span=50).mean()
    position = np.sign(ema20 - ema50)
    return position.reindex(test_df.index).fillna(0.0)


def volatility_regime(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    """Cheap, deterministic causal regime labels for stability metrics.

    Classifies each test bar by where its trailing realized vol sits relative to
    the train-window vol terciles -> LOW / MED / HIGH. Used only to exercise the
    regime-stability metrics without the cost of fitting an HMM per fold.
    """
    combined = pd.concat([train_df, test_df])["Close"].astype(float)
    rv = combined.pct_change().rolling(20).std()
    train_rv = rv.reindex(train_df.index).dropna()
    if train_rv.empty:
        return pd.Series(["MED"] * len(test_df), index=test_df.index)
    lo, hi = np.quantile(train_rv, [1 / 3, 2 / 3])
    test_rv = rv.reindex(test_df.index)
    labels = np.where(test_rv <= lo, "LOW", np.where(test_rv >= hi, "HIGH", "MED"))
    return pd.Series(labels, index=test_df.index)


@dataclass
class FoldResult:
    fold_id: int
    train_start: str
    test_start: str
    test_end: str
    n_test: int
    sharpe: float
    avg_return: float
    hit_rate: float


@dataclass
class ValidationReport:
    engine: str
    asset: str
    timeframe: str
    periods_per_year: int
    n_folds: int
    splitter: dict
    oos: OOSMetrics
    folds: list[FoldResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "asset": self.asset,
            "timeframe": self.timeframe,
            "periods_per_year": self.periods_per_year,
            "n_folds": self.n_folds,
            "splitter": self.splitter,
            "oos_metrics": self.oos.to_dict(),
            "folds": [
                {
                    "fold_id": f.fold_id,
                    "train_start": f.train_start,
                    "test_start": f.test_start,
                    "test_end": f.test_end,
                    "n_test": f.n_test,
                    "sharpe": round(f.sharpe, 4),
                    "avg_return": round(f.avg_return, 6),
                    "hit_rate": round(f.hit_rate, 4),
                }
                for f in self.folds
            ],
            "notes": self.notes,
        }


def _regime_matrix(labels: list[str]) -> np.ndarray:
    model = build_transition_model(labels)
    states = model.states
    n = len(states)
    mat = np.zeros((n, n))
    for i, a in enumerate(states):
        for j, b in enumerate(states):
            mat[i, j] = model.matrix.get(a, {}).get(b, 0.0)
    return mat


class ValidationFramework:
    def __init__(self, *, n_trials: int = 1) -> None:
        self._n_trials = n_trials

    def evaluate(
        self,
        df: pd.DataFrame,
        *,
        engine_name: str,
        asset: str,
        timeframe: str,
        periods_per_year: int = 252,
        splitter: WalkForwardSplitter | None = None,
        signal_fn: SignalFn = ema_trend_signal,
        regime_fn: RegimeFn | None = volatility_regime,
    ) -> ValidationReport:
        n = len(df)
        splitter = splitter or WalkForwardSplitter(
            train_size=max(60, n // 4),
            test_size=max(20, n // 10),
            expanding=True,
            purge=1,
        )
        close = df["Close"].astype(float)
        fwd = _forward_returns(close)

        all_positions: list[float] = []
        all_fwd: list[float] = []
        all_strat: list[float] = []
        all_regime_labels: list[str] = []
        fold_matrices: list[np.ndarray] = []
        fold_results: list[FoldResult] = []
        notes: list[str] = []

        folds: list[Fold] = list(splitter.split(n))
        for fold in folds:
            test_df = df.iloc[fold.test_idx]
            train_df = df.iloc[fold.train_idx]

            positions = signal_fn(train_df, test_df).reindex(test_df.index).fillna(0.0)
            fwd_test = fwd.reindex(test_df.index).fillna(0.0)
            strat = positions * fwd_test

            all_positions.extend(positions.tolist())
            all_fwd.extend(fwd_test.tolist())
            all_strat.extend(strat.tolist())

            if regime_fn is not None:
                labels = regime_fn(train_df, test_df)
                lbls = [str(x) for x in labels.tolist()]
                all_regime_labels.extend(lbls)
                fold_matrices.append(_regime_matrix(lbls))

            fold_results.append(
                FoldResult(
                    fold_id=fold.fold_id,
                    train_start=str(df.index[fold.train_idx[0]]),
                    test_start=str(df.index[fold.test_idx[0]]),
                    test_end=str(df.index[fold.test_idx[-1]]),
                    n_test=len(test_df),
                    sharpe=sharpe_ratio(strat, periods_per_year),
                    avg_return=avg_return(strat),
                    hit_rate=hit_rate(positions, fwd_test),
                )
            )

        if not all_strat:
            notes.append("No OOS folds produced — insufficient data for splitter config.")

        strat_arr = np.asarray(all_strat, dtype=float)
        oos = OOSMetrics(
            hit_rate=hit_rate(pd.Series(all_positions), pd.Series(all_fwd)),
            avg_return=avg_return(strat_arr),
            max_drawdown=max_drawdown(strat_arr),
            sharpe=sharpe_ratio(strat_arr, periods_per_year),
            probabilistic_sharpe=probabilistic_sharpe_ratio(
                strat_arr, periods_per_year=periods_per_year
            ),
            deflated_sharpe=deflated_sharpe_ratio(
                strat_arr, n_trials=self._n_trials, periods_per_year=periods_per_year
            ),
            regime_persistence=regime_persistence(all_regime_labels),
            transition_stability=transition_stability(fold_matrices),
            n_observations=int(strat_arr.size),
        )

        return ValidationReport(
            engine=engine_name,
            asset=asset,
            timeframe=timeframe,
            periods_per_year=periods_per_year,
            n_folds=len(folds),
            splitter={
                "train_size": splitter.train_size,
                "test_size": splitter.test_size,
                "expanding": splitter.expanding,
                "purge": splitter.purge,
                "embargo": splitter.embargo,
            },
            oos=oos,
            folds=fold_results,
            notes=notes,
        )
