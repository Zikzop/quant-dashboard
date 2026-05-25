import pandas as pd
import numpy as np

from research.performance_metrics import calculate_performance_metrics

from engines.garch_engine import calculate_garch_volatility

from engines.hmm_regime_engine import HMMRegimeEngine

hmm_engine = HMMRegimeEngine()


def run_backtest(df):

    df = df.copy()

    # =========================
    # EMA STRUCTURE
    # =========================

    close = df["Close"]

    df["EMA20"] = close.ewm(span=20).mean()

    df["EMA50"] = close.ewm(span=50).mean()

    # =========================
    # RETURNS
    # =========================

    df["returns"] = close.pct_change()

    # =========================
    # HMM REGIME
    # =========================

    hmm_data = hmm_engine.classify_regimes(df)

    # =========================
    # GARCH REGIME
    # =========================

    garch_data = calculate_garch_volatility(close)

    # =========================
    # POSITION ENGINE
    # =========================

    df["position"] = 0

    # LONG CONDITIONS
    long_condition = (
        (df["Close"] > df["EMA20"])
        & (df["EMA20"] > df["EMA50"])
        & (hmm_data["trend_probability"] > 60)
        & (hmm_data["crisis_probability"] < 25)
        & (garch_data["vol_regime"] != "EXPANDING_VOL")
    )

    # SHORT CONDITIONS
    short_condition = (
        (df["Close"] < df["EMA20"])
        & (df["EMA20"] < df["EMA50"])
        & (hmm_data["crisis_probability"] > 40)
    )

    df.loc[long_condition, "position"] = 1

    df.loc[short_condition, "position"] = -1

    # =========================
    # STRATEGY RETURNS
    # =========================

    df["strategy_returns"] = df["position"].shift(1) * df["returns"]

    df = df.dropna()

    # =========================
    # EQUITY CURVE
    # =========================

    df["equity_curve"] = (1 + df["strategy_returns"]).cumprod()

    # =========================
    # PERFORMANCE METRICS
    # =========================

    metrics = calculate_performance_metrics(df["strategy_returns"])

    return {
        "metrics": metrics,
        "equity_curve": df["equity_curve"].tolist(),
        "returns": df["strategy_returns"].tolist(),
    }
