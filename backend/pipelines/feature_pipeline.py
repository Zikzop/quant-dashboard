"""
Research feature generation on normalized OHLCV.

All rolling statistics use backward-looking windows only (no lookahead).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeaturePipelineConfig:
    vol_window: int = 20
    mean_window: int = 20
    zscore_window: int = 20
    atr_window: int = 14
    realized_vol_annualization: float = 252.0


class FeaturePipeline:
    """Generate institutional research features from normalized OHLCV."""

    def __init__(self, config: FeaturePipelineConfig | None = None) -> None:
        self.config = config or FeaturePipelineConfig()

    def run(self, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Parameters
        ----------
        ohlcv : pd.DataFrame
            Normalized lowercase OHLCV, UTC DatetimeIndex.

        Returns
        -------
        pd.DataFrame
            OHLCV columns plus research features.
        """
        self._validate_input(ohlcv)
        cfg = self.config

        out = ohlcv.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        out["log_return"] = np.log(close / close.shift(1))
        out["pct_return"] = close.pct_change()

        out["rolling_mean"] = close.rolling(cfg.mean_window, min_periods=cfg.mean_window).mean()

        rolling_std = close.rolling(cfg.zscore_window, min_periods=cfg.zscore_window).std()
        out["z_score"] = (close - out["rolling_mean"]) / rolling_std

        out["rolling_volatility"] = (
            out["log_return"]
            .rolling(cfg.vol_window, min_periods=cfg.vol_window)
            .std()
            * np.sqrt(cfg.realized_vol_annualization)
        )

        out["realized_volatility"] = out["rolling_volatility"]

        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)

        out["atr"] = tr.rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()

        logger.info(
            "Generated features rows=%d columns=%d",
            len(out),
            len(out.columns),
        )
        return out

    @staticmethod
    def _validate_input(df: pd.DataFrame) -> None:
        required = {"open", "high", "low", "close", "volume"}
        cols = {str(c).lower() for c in df.columns}
        missing = required - cols
        if missing:
            raise ValueError(f"Feature pipeline missing columns: {sorted(missing)}")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Feature pipeline requires DatetimeIndex")
