import numpy as np
import pandas as pd

from arch import arch_model


def calculate_garch_volatility_series(
    close_prices: pd.Series,
    vol_slope_window: int = 5,
) -> pd.DataFrame:
    """
    Historical GARCH(1,1) conditional volatility aligned to price index.

    Each conditional_vol[t] is computed from the fitted GARCH recursion using
    returns up to t (no future returns enter sigma_t). Model parameters are
    estimated once via MLE on the full return sample (see integrity report).
    """
    close = close_prices.squeeze()
    returns = 100 * np.log(close / close.shift(1)).dropna()

    model = arch_model(returns, vol="Garch", p=1, q=1, rescale=False)
    results = model.fit(disp="off")

    conditional_vol = results.conditional_volatility
    vol_slope = conditional_vol - conditional_vol.shift(vol_slope_window)

    vol_regime = pd.Series(
        np.where(vol_slope > 0, "EXPANDING_VOL", "CONTRACTING_VOL"),
        index=conditional_vol.index,
    )

    series = pd.DataFrame(
        {
            "garch_vol": conditional_vol,
            "vol_slope": vol_slope,
            "vol_regime": vol_regime,
        },
        index=conditional_vol.index,
    )

    return series.reindex(close.index)


def calculate_garch_volatility(close_prices):

    series = calculate_garch_volatility_series(close_prices)

    if series.empty or series["garch_vol"].dropna().empty:
        return {
            "garch_vol": 0.0,
            "vol_regime": "CONTRACTING_VOL",
            "vol_slope": 0.0,
        }

    latest = series.dropna(subset=["garch_vol"]).iloc[-1]

    return {
        "garch_vol": round(float(latest["garch_vol"]), 2),
        "vol_regime": str(latest["vol_regime"]),
        "vol_slope": round(float(latest["vol_slope"]), 2)
        if not pd.isna(latest["vol_slope"])
        else 0.0,
    }
