"""
Cross-sectional ranking engine — universe-agnostic multi-asset scoring.

Supports any asset class universe passed as wide DataFrame (symbols as columns).
No hardcoded tickers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RankMethod = Literal["percentile", "zscore", "raw"]


@dataclass(frozen=True)
class RankingConfig:
    lookback: int = 60
    min_periods: int | None = None
    method: RankMethod = "percentile"
    vol_adjust: bool = True


@dataclass(frozen=True)
class CrossSectionalRankResult:
    scores: pd.DataFrame
    ranks: pd.DataFrame
    universe_size: pd.Series
    summary: str
    warnings: tuple[str, ...]


class CrossSectionalRankingEngine:
    """
    Rank assets cross-sectionally on causal momentum or custom metric.

    Input: wide DataFrame of prices or returns (index=time, columns=symbols).
    """

    def __init__(self, config: RankingConfig | None = None) -> None:
        self.config = config or RankingConfig()

    def rank(
        self,
        prices: pd.DataFrame,
        *,
        metric: Literal["momentum", "vol_adj_momentum"] = "momentum",
    ) -> CrossSectionalRankResult:
        cfg = self.config
        min_p = cfg.min_periods or cfg.lookback
        warnings: list[str] = []

        if prices.empty or prices.shape[1] < 2:
            warnings.append("Universe size < 2; cross-sectional ranking degraded.")

        returns = prices.pct_change()
        if metric == "momentum":
            raw = prices.pct_change(cfg.lookback)
        else:
            cum = returns.rolling(cfg.lookback, min_periods=min_p).sum()
            vol = returns.rolling(cfg.lookback, min_periods=min_p).std().replace(0, np.nan)
            raw = cum / vol

        if cfg.vol_adjust and metric == "momentum":
            vol = returns.rolling(cfg.lookback, min_periods=min_p).std().replace(0, np.nan)
            raw = raw / vol

        scores = self._cross_sectional_score(raw, cfg.method)
        ranks = scores.rank(axis=1, ascending=False, method="average")
        universe = scores.notna().sum(axis=1)

        summary = (
            f"Ranked {prices.shape[1]} symbols over {len(prices)} periods "
            f"method={cfg.method} metric={metric}."
        )

        return CrossSectionalRankResult(
            scores=scores,
            ranks=ranks,
            universe_size=universe,
            summary=summary,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _cross_sectional_score(raw: pd.DataFrame, method: RankMethod) -> pd.DataFrame:
        if method == "raw":
            return raw
        if method == "zscore":
            mean = raw.mean(axis=1)
            std = raw.std(axis=1).replace(0, np.nan)
            return raw.sub(mean, axis=0).div(std, axis=0)
        return raw.rank(axis=1, pct=True)
