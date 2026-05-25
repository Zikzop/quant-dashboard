"""
Institutional cross-asset correlation engine.

Computes rolling correlation structure, BTC betas, covariance instability,
z-scored correlations, and regime-sensitive shifts from live yfinance data.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

# Canonical cross-asset universe
ASSET_UNIVERSE: Dict[str, str] = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SPY": "SPY",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "GOLD": "GC=F",
    "TNX": "^TNX",
}

DEFAULT_WINDOW = 60
ZSCORE_LOOKBACK = 252
SHORT_REGIME_WINDOW = 20


def _flatten_yfinance_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_aligned_closes(
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    """Download and align close prices for the full asset universe."""
    series: Dict[str, pd.Series] = {}

    for label, ticker in ASSET_UNIVERSE.items():
        raw = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if raw.empty:
            continue

        raw = _flatten_yfinance_columns(raw)
        close = raw["Close"].squeeze()
        close.name = label
        series[label] = close

    if not series:
        raise ValueError("No cross-asset price data returned from yfinance.")

    prices = pd.DataFrame(series).sort_index().ffill().dropna(how="any")
    return prices


def _log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log(prices / prices.shift(1)).dropna(how="any")


def _matrix_to_nested_dict(
    matrix: pd.DataFrame,
    precision: int = 4,
) -> Dict[str, Dict[str, Optional[float]]]:
    assets = list(matrix.columns)
    out: Dict[str, Dict[str, Optional[float]]] = {}

    for row in assets:
        out[row] = {}
        for col in assets:
            value = matrix.loc[row, col]
            if pd.isna(value):
                out[row][col] = None
            else:
                out[row][col] = round(float(value), precision)

    return out


def _rolling_pairwise_correlation_series(
    returns: pd.DataFrame,
    window: int,
) -> Dict[str, pd.Series]:
    """Rolling correlation of each asset vs BTC."""
    btc = returns["BTC"]
    series: Dict[str, pd.Series] = {}

    for asset in returns.columns:
        if asset == "BTC":
            series[asset] = pd.Series(1.0, index=returns.index)
        else:
            series[asset] = returns[asset].rolling(window).corr(btc)

    return series


def _zscore_latest(series: pd.Series, lookback: int) -> float:
    history = series.dropna().tail(lookback)
    if len(history) < 10:
        return 0.0

    latest = float(history.iloc[-1])
    mean = float(history.mean())
    std = float(history.std())

    if std == 0 or np.isnan(std):
        return 0.0

    return (latest - mean) / std


def _rolling_beta_vs_btc(
    returns: pd.DataFrame,
    window: int,
) -> pd.Series:
    btc = returns["BTC"]
    betas: Dict[str, float] = {}

    btc_var = btc.rolling(window).var()

    for asset in returns.columns:
        if asset == "BTC":
            betas[asset] = 1.0
            continue

        cov = returns[asset].rolling(window).cov(btc)
        beta = cov / btc_var
        betas[asset] = float(beta.iloc[-1]) if not pd.isna(beta.iloc[-1]) else 0.0

    return pd.Series(betas)


def _covariance_instability(
    returns: pd.DataFrame,
    window: int,
) -> Dict[str, float | str]:
    """
    Frobenius-normalized shift between recent and prior covariance windows.
    """
    if len(returns) < window * 2:
        window = max(20, len(returns) // 2)

    recent = returns.tail(window)
    prior = returns.iloc[-(2 * window):-window]

    if prior.empty or recent.empty:
        return {
            "score": 0.0,
            "regime": "STABLE",
            "frobenius_delta": 0.0,
        }

    recent_cov = recent.cov()
    prior_cov = prior.cov()

    delta = recent_cov.values - prior_cov.values
    frob_delta = float(np.linalg.norm(delta, ord="fro"))
    prior_norm = float(np.linalg.norm(prior_cov.values, ord="fro"))

    score = frob_delta / prior_norm if prior_norm > 0 else frob_delta

    if score >= 0.35:
        regime = "UNSTABLE"
    elif score >= 0.18:
        regime = "ELEVATED"
    else:
        regime = "STABLE"

    return {
        "score": round(score, 4),
        "regime": regime,
        "frobenius_delta": round(frob_delta, 4),
    }


def _regime_correlation_shift(
    returns: pd.DataFrame,
    regime_label: Optional[str],
    short_window: int = SHORT_REGIME_WINDOW,
    long_window: int = DEFAULT_WINDOW,
) -> Dict:
    short_corr = returns.tail(short_window).corr()
    long_corr = returns.tail(long_window).corr()

    assets = list(returns.columns)
    shifts: List[Dict] = []

    for i, a in enumerate(assets):
        for b in assets[i + 1:]:
            long_value = long_corr.loc[a, b]
            short_value = short_corr.loc[a, b]

            if pd.isna(long_value) or pd.isna(short_value):
                continue

            delta = float(short_value - long_value)
            shifts.append(
                {
                    "pair": f"{a}-{b}",
                    "long_correlation": round(long_value, 4),
                    "short_correlation": round(short_value, 4),
                    "delta": round(delta, 4),
                }
            )

    shifts.sort(key=lambda row: abs(row["delta"]), reverse=True)

    magnitude = float(
        np.mean([abs(row["delta"]) for row in shifts]) if shifts else 0.0
    )

    sensitivity = "LOW"
    if regime_label in ("CRISIS", "MEAN_REVERT") and magnitude >= 0.12:
        sensitivity = "HIGH"
    elif magnitude >= 0.08:
        sensitivity = "MODERATE"

    return {
        "current_regime": regime_label,
        "shift_magnitude": round(magnitude, 4),
        "sensitivity": sensitivity,
        "largest_shifts": shifts[:6],
    }


def _build_heatmap_cells(
    returns: pd.DataFrame,
    zscore_matrix: pd.DataFrame,
    betas: pd.Series,
) -> List[Dict]:
    cells: List[Dict] = []

    for asset in returns.columns:
        daily_return = float(returns[asset].iloc[-1] * 100)
        z_btc = float(zscore_matrix.loc[asset, "BTC"]) if asset != "BTC" else 0.0

        cells.append(
            {
                "asset": asset,
                "daily_return_pct": round(daily_return, 2),
                "beta_vs_btc": round(float(betas[asset]), 4),
                "correlation_zscore_vs_btc": round(z_btc, 4),
            }
        )

    return cells


def calculate_correlation_intelligence(
    regime_label: Optional[str] = None,
    window: int = DEFAULT_WINDOW,
    period: str = "2y",
) -> Dict:
    """
    Full cross-asset correlation intelligence payload for API / UI.
    """
    prices = fetch_aligned_closes(period=period)
    returns = _log_returns(prices)

    assets = list(returns.columns)

    latest_corr = pd.DataFrame(
        np.nan,
        index=assets,
        columns=assets,
    )

    for row in assets:
        for col in assets:
            if row == col:
                latest_corr.loc[row, col] = 1.0
            else:
                pair = returns[row].rolling(window).corr(returns[col])
                latest_corr.loc[row, col] = pair.iloc[-1]

    corr_series = _rolling_pairwise_correlation_series(returns, window)

    zscore_matrix = pd.DataFrame(
        np.zeros((len(assets), len(assets))),
        index=assets,
        columns=assets,
    )

    for a in assets:
        for b in assets:
            if a == b:
                zscore_matrix.loc[a, b] = 0.0
                continue

            pair = returns[a].rolling(window).corr(returns[b])
            zscore_matrix.loc[a, b] = _zscore_latest(pair, ZSCORE_LOOKBACK)

    betas = _rolling_beta_vs_btc(returns, window)
    instability = _covariance_instability(returns, window)
    regime_shift = _regime_correlation_shift(
        returns,
        regime_label=regime_label,
    )

    matrix_values = [
        [
            None if pd.isna(latest_corr.loc[row, col]) else round(float(latest_corr.loc[row, col]), 4)
            for col in assets
        ]
        for row in assets
    ]

    zscore_values = [
        [
            round(float(zscore_matrix.loc[row, col]), 4)
            for col in assets
        ]
        for row in assets
    ]

    return {
        "assets": assets,
        "window": window,
        "correlation_matrix": _matrix_to_nested_dict(latest_corr),
        "correlation_zscore_matrix": _matrix_to_nested_dict(zscore_matrix, precision=4),
        "matrix_labels": assets,
        "matrix_values": matrix_values,
        "zscore_matrix_values": zscore_values,
        "beta_vs_btc": {
            asset: round(float(betas[asset]), 4) for asset in assets
        },
        "covariance_instability": instability,
        "regime_correlation_shift": regime_shift,
        "heatmap_cells": _build_heatmap_cells(returns, zscore_matrix, betas),
    }
