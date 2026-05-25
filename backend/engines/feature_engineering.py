import numpy as np
import pandas as pd


def build_hmm_features(df):

    df = df.copy()

    # LOG RETURNS
    df["log_returns"] = np.log(df["Close"] / df["Close"].shift(1))

    # REALIZED VOLATILITY
    df["realized_vol"] = df["log_returns"].rolling(20).std() * np.sqrt(252)

    # MOMENTUM
    df["momentum"] = ((df["Close"] / df["Close"].shift(20)) - 1) * 100

    # RANGE EXPANSION
    df["range_expansion"] = (df["High"] - df["Low"]) / df["Close"]

    # CLEAN NaNs
    df = df.dropna()

    features = df[
        [
            "log_returns",
            "realized_vol",
            "momentum",
            "range_expansion",
        ]
    ]

    return features
