import numpy as np
import pandas as pd

from arch import arch_model


def calculate_garch_volatility(close_prices):

    returns = 100 * np.log(close_prices / close_prices.shift(1)).dropna()

    model = arch_model(returns, vol="Garch", p=1, q=1, rescale=False)

    results = model.fit(disp="off")

    conditional_vol = results.conditional_volatility

    latest_vol = conditional_vol.iloc[-1]

    vol_slope = conditional_vol.iloc[-1] - conditional_vol.iloc[-5]

    if vol_slope > 0:
        vol_regime = "EXPANDING_VOL"

    else:
        vol_regime = "CONTRACTING_VOL"

    return {
        "garch_vol": round(float(latest_vol), 2),
        "vol_regime": vol_regime,
        "vol_slope": round(float(vol_slope), 2),
    }
