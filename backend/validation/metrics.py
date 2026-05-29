"""
Out-of-sample performance and regime-stability metrics.

All metrics are pure functions over arrays/series so they can be unit-tested
against known closed-form answers. Statistical honesty is a first-class goal
here: the deflated Sharpe entry is explicitly flagged as a placeholder that
accounts for a *single* trial unless told otherwise, because a naive Sharpe on
a strategy selected from many trials is one of the most common ways research
overstates edge.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


def _clean(returns: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(returns, dtype=float)
    return arr[np.isfinite(arr)]


def hit_rate(positions: pd.Series, forward_returns: pd.Series) -> float:
    """Fraction of directional bets whose sign matched the forward return."""
    pos = np.asarray(positions, dtype=float)
    fwd = np.asarray(forward_returns, dtype=float)
    mask = np.isfinite(pos) & np.isfinite(fwd) & (pos != 0)
    if mask.sum() == 0:
        return 0.0
    correct = np.sign(pos[mask]) == np.sign(fwd[mask])
    return float(correct.mean())


def avg_return(strategy_returns: pd.Series | np.ndarray) -> float:
    arr = _clean(strategy_returns)
    return float(arr.mean()) if arr.size else 0.0


def max_drawdown(strategy_returns: pd.Series | np.ndarray) -> float:
    """Maximum peak-to-trough drawdown of the compounded equity curve (>=0)."""
    arr = _clean(strategy_returns)
    if arr.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + arr)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    return float(-drawdowns.min())


def sharpe_ratio(
    strategy_returns: pd.Series | np.ndarray,
    periods_per_year: int = 252,
    risk_free: float = 0.0,
) -> float:
    arr = _clean(strategy_returns)
    if arr.size < 2:
        return 0.0
    excess = arr - risk_free / periods_per_year
    std = excess.std(ddof=1)
    if std == 0:
        return 0.0
    return float(excess.mean() / std * math.sqrt(periods_per_year))


def probabilistic_sharpe_ratio(
    strategy_returns: pd.Series | np.ndarray,
    benchmark_sr: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """PSR: probability the true (annualized) Sharpe exceeds ``benchmark_sr``,
    correcting for skew and kurtosis of the return distribution.
    """
    arr = _clean(strategy_returns)
    n = arr.size
    if n < 3:
        return 0.0
    sr_period = sharpe_ratio(arr, periods_per_year=1)  # per-period SR
    bench_period = benchmark_sr / math.sqrt(periods_per_year)
    skew = float(stats.skew(arr))
    kurt = float(stats.kurtosis(arr, fisher=False))  # non-excess kurtosis
    denom = 1.0 - skew * sr_period + ((kurt - 1.0) / 4.0) * sr_period**2
    if denom <= 0:
        return 0.0
    psr = stats.norm.cdf((sr_period - bench_period) * math.sqrt(n - 1) / math.sqrt(denom))
    return float(psr)


def deflated_sharpe_ratio(
    strategy_returns: pd.Series | np.ndarray,
    n_trials: int = 1,
    periods_per_year: int = 252,
) -> dict:
    """Deflated Sharpe Ratio (placeholder).

    Approximates the expected maximum Sharpe under ``n_trials`` independent
    strategy configurations (Bailey & López de Prado) and reports the PSR
    against that inflated benchmark. With ``n_trials=1`` it reduces to the PSR
    against zero. A full implementation requires the variance of trial Sharpes
    and is deferred (hence "placeholder"), but the multiple-testing correction
    is wired so callers can already pass a realistic trial count.
    """
    arr = _clean(strategy_returns)
    if arr.size < 3:
        return {"deflated_sharpe": 0.0, "expected_max_sharpe": 0.0, "n_trials": n_trials, "placeholder": True}

    if n_trials > 1:
        euler_mascheroni = 0.5772156649
        e_max_z = (1 - euler_mascheroni) * stats.norm.ppf(1 - 1.0 / n_trials) + (
            euler_mascheroni * stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
        )
        # Scale the expected-max standardized value by the per-period Sharpe
        # estimation noise (~1/sqrt(n)); without observed trial Sharpes this is
        # the standard placeholder proxy for their cross-sectional dispersion.
        expected_max_sr = float(e_max_z) / math.sqrt(arr.size)  # per-period SR units
    else:
        expected_max_sr = 0.0

    dsr = probabilistic_sharpe_ratio(
        arr,
        benchmark_sr=expected_max_sr * math.sqrt(periods_per_year),
        periods_per_year=periods_per_year,
    )
    return {
        "deflated_sharpe": round(dsr, 4),
        "expected_max_sharpe": round(expected_max_sr * math.sqrt(periods_per_year), 4),
        "n_trials": n_trials,
        "placeholder": True,
    }


def regime_persistence(regime_labels: pd.Series | list) -> dict:
    """Average run-length (in bars) per regime + overall persistence ratio.

    Persistence ratio = P(label_{t+1} == label_t), i.e. the diagonal mass of the
    empirical transition matrix. High persistence => stable regimes.
    """
    labels = [str(x) for x in list(regime_labels) if x is not None and str(x) not in {"nan", "UNKNOWN", ""}]
    if len(labels) < 2:
        return {"persistence_ratio": 0.0, "avg_run_length": {}, "n": len(labels)}

    stays = sum(1 for a, b in zip(labels[:-1], labels[1:]) if a == b)
    persistence_ratio = stays / (len(labels) - 1)

    runs: dict[str, list[int]] = {}
    current = labels[0]
    length = 1
    for lab in labels[1:]:
        if lab == current:
            length += 1
        else:
            runs.setdefault(current, []).append(length)
            current, length = lab, 1
    runs.setdefault(current, []).append(length)
    avg_run = {k: round(float(np.mean(v)), 2) for k, v in runs.items()}
    return {
        "persistence_ratio": round(persistence_ratio, 4),
        "avg_run_length": avg_run,
        "n": len(labels),
    }


def transition_stability(matrices: list[np.ndarray]) -> float:
    """Stability of transition matrices across folds, in [0, 1].

    Defined as 1 - mean pairwise (consecutive) normalized Frobenius distance.
    1.0 => transition structure is identical across folds (stable); lower =>
    the regime dynamics themselves are drifting (a model-risk red flag).
    """
    valid = [m for m in matrices if m is not None and m.size > 0]
    if len(valid) < 2:
        return 1.0
    shape = valid[0].shape
    valid = [m for m in valid if m.shape == shape]
    if len(valid) < 2:
        return 1.0
    max_dist = math.sqrt(2.0 * shape[0])  # bound on Frobenius dist of two stochastic matrices
    dists = [
        np.linalg.norm(valid[i] - valid[i - 1], ord="fro") / max_dist
        for i in range(1, len(valid))
    ]
    return float(max(0.0, 1.0 - np.mean(dists)))


@dataclass
class OOSMetrics:
    hit_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    probabilistic_sharpe: float = 0.0
    deflated_sharpe: dict = field(default_factory=dict)
    regime_persistence: dict = field(default_factory=dict)
    transition_stability: float = 1.0
    n_observations: int = 0

    def to_dict(self) -> dict:
        return {
            "hit_rate": round(self.hit_rate, 4),
            "avg_return": round(self.avg_return, 6),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe": round(self.sharpe, 4),
            "probabilistic_sharpe": round(self.probabilistic_sharpe, 4),
            "deflated_sharpe": self.deflated_sharpe,
            "regime_persistence": self.regime_persistence,
            "transition_stability": round(self.transition_stability, 4),
            "n_observations": self.n_observations,
        }
