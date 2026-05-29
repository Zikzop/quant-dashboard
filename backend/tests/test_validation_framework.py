"""Validation framework tests: splitter, closed-form metrics, OOS report (P0.5)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from validation.framework import ValidationFramework
from validation.metrics import (
    hit_rate,
    max_drawdown,
    regime_persistence,
    sharpe_ratio,
    transition_stability,
)
from validation.walk_forward import WalkForwardSplitter


def test_walk_forward_fold_count_and_no_leakage():
    splitter = WalkForwardSplitter(train_size=100, test_size=20, expanding=True, purge=0)
    folds = list(splitter.split(200))
    assert len(folds) == 5
    for f in folds:
        # purge=0 -> train ends exactly where test begins (no overlap).
        assert f.train_idx.max() < f.test_idx.min()


def test_walk_forward_purge_removes_adjacent_train():
    splitter = WalkForwardSplitter(train_size=100, test_size=20, expanding=True, purge=5)
    fold = next(iter(splitter.split(200)))
    assert fold.train_idx.max() <= fold.test_idx.min() - 5


def test_hit_rate_closed_form():
    positions = pd.Series([1, 1, -1, 0])
    fwd = pd.Series([0.1, -0.1, -0.1, 0.5])
    assert abs(hit_rate(positions, fwd) - (2 / 3)) < 1e-9


def test_max_drawdown_closed_form():
    returns = np.array([0.1, -0.5])
    assert abs(max_drawdown(returns) - 0.5) < 1e-9


def test_sharpe_zero_variance():
    assert sharpe_ratio(np.array([0.01, 0.01, 0.01])) == 0.0


def test_regime_persistence_closed_form():
    rp = regime_persistence(["A", "A", "B"])
    assert abs(rp["persistence_ratio"] - 0.5) < 1e-9
    assert rp["avg_run_length"]["A"] == 2.0


def test_transition_stability_identical_matrices():
    m = np.array([[0.8, 0.2], [0.3, 0.7]])
    assert transition_stability([m, m, m]) == 1.0


def test_framework_runs_and_is_deterministic():
    rng = np.random.default_rng(11)
    n = 500
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, n)))
    df = pd.DataFrame(
        {"Open": close, "High": close * 1.004, "Low": close * 0.996, "Close": close, "Volume": 1000.0},
        index=idx,
    )
    fw = ValidationFramework(n_trials=10)
    kwargs = dict(
        engine_name="ema_trend",
        asset="BTC",
        timeframe="1D",
        periods_per_year=365,
        splitter=WalkForwardSplitter(train_size=120, test_size=40, purge=1),
    )
    r1 = fw.evaluate(df, **kwargs).to_dict()
    r2 = fw.evaluate(df, **kwargs).to_dict()
    assert r1 == r2
    assert r1["n_folds"] >= 1
    oos = r1["oos_metrics"]
    assert 0.0 <= oos["hit_rate"] <= 1.0
    assert oos["max_drawdown"] >= 0.0
    assert "deflated_sharpe" in oos and oos["deflated_sharpe"]["placeholder"] is True
    assert 0.0 <= oos["transition_stability"] <= 1.0
