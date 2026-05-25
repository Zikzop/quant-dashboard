from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import yfinance as yf
import pandas as pd
import numpy as np

from engines.adx_engine import (
    ADXRegimeEngine,
    adx_result_to_dict,
)

from engines.market_state_engine import build_market_state

from engines.garch_engine import (
    calculate_garch_volatility,
    calculate_garch_volatility_series,
)

from engines.hmm_regime_engine import HMMRegimeEngine

from engines.signal_engine import calculate_signal_engine

from engines.correlation_engine import calculate_correlation_intelligence

app = FastAPI()

hmm_engine = HMMRegimeEngine()

adx_engine = ADXRegimeEngine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/market")
def get_market():

    symbol = "BTC-USD"

    df = yf.download(symbol, period="2y", interval="1d")

    df.columns = df.columns.get_level_values(0)

    close = df["Close"].squeeze()

    # =========================
    # TECHNICAL STRUCTURE
    # =========================

    df["EMA20"] = close.ewm(span=20).mean()
    df["EMA50"] = close.ewm(span=50).mean()

    returns = close.pct_change()

    volatility = returns.std() * np.sqrt(252)

    current_price = float(close.iloc[-1])

    ema20 = float(df["EMA20"].iloc[-1])
    ema50 = float(df["EMA50"].iloc[-1])

    # =========================
    # TREND ENGINE
    # =========================

    trend = "RANGING"

    if current_price > ema20 and ema20 > ema50:
        trend = "BULLISH"

    elif current_price < ema20 and ema20 < ema50:
        trend = "BEARISH"

    # =========================
    # MOMENTUM
    # =========================

    momentum = ((current_price / float(close.iloc[-20])) - 1) * 100

    # =========================
    # GARCH ENGINE
    # =========================

    # =========================
    # HISTORICAL ENGINE SERIES
    # =========================

    adx_history = adx_engine.compute_per_bar_series(df)
    garch_history = calculate_garch_volatility_series(close)

    garch_latest = garch_history.dropna(subset=["garch_vol"]).iloc[-1]
    garch_data = {
        "garch_vol": round(float(garch_latest["garch_vol"]), 2),
        "vol_regime": str(garch_latest["vol_regime"]),
        "vol_slope": round(float(garch_latest["vol_slope"]), 2)
        if not pd.isna(garch_latest["vol_slope"])
        else 0.0,
    }
    chart_index = df.tail(30).index
    hmm_chart = hmm_engine.compute_historical_regimes(df, index=chart_index)

    hmm_data = hmm_engine.classify_regimes(df)

    correlation_data = calculate_correlation_intelligence(
        regime_label=hmm_data["regime_label"],
    )

    # =========================
    # MARKET REGIME
    # =========================

    structure_regime = "RANGING"

    if garch_data["vol_regime"] == "EXPANDING_VOL":
        structure_regime = "VOLATILE"

    if trend == "BULLISH" and momentum > 5:
        structure_regime = "TRENDING_BULL"

    elif trend == "BEARISH" and momentum < -5:
        structure_regime = "TRENDING_BEAR"

    # =========================
    # SIGNAL ENGINE
    # =========================

    signal_data = calculate_signal_engine(
        trend=trend,
        momentum=momentum,
        volatility=volatility,
        hmm_data=hmm_data,
        garch_data=garch_data,
    )

    # =========================
    # CHART DATA (per-bar historical intelligence)
    # =========================

    adx_latest = adx_engine.compute_latest(df)
    adx_result = adx_result_to_dict(adx_latest)

    chart_data = []

    for index, row in df.tail(30).iterrows():

        adx_row = adx_history.loc[index]
        garch_row = garch_history.loc[index]
        hmm_row = (
            hmm_chart.loc[index]
            if index in hmm_chart.index
            else pd.Series(dtype=object)
        )

        bar = {
            "time": index.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "ema20": round(float(row["EMA20"]), 2),
            "ema50": round(float(row["EMA50"]), 2),
        }

        if not pd.isna(adx_row.get("adx")):
            bar["adx"] = round(float(adx_row["adx"]), 2)
            bar["plus_di"] = round(float(adx_row["plus_di"]), 2)
            bar["minus_di"] = round(float(adx_row["minus_di"]), 2)
            bar["direction"] = adx_row["direction"]
            bar["trend_strength"] = adx_row["trend_strength"]

        if not pd.isna(garch_row.get("garch_vol")):
            bar["garch_vol"] = round(float(garch_row["garch_vol"]), 4)
            bar["vol_regime"] = str(garch_row["vol_regime"])

        if hmm_row.get("hmm_regime") is not None and not (
            isinstance(hmm_row.get("hmm_regime"), float)
            and pd.isna(hmm_row.get("hmm_regime"))
        ):
            bar["hmm_regime"] = str(hmm_row["hmm_regime"])
            bar["mean_revert_probability"] = round(
                float(hmm_row["mean_revert_probability"]), 4
            )
            bar["trend_probability"] = round(
                float(hmm_row["trend_probability"]), 4
            )
            bar["crisis_probability"] = round(
                float(hmm_row["crisis_probability"]), 4
            )

        chart_data.append(bar)

    market_state = build_market_state(
        adx_result=adx_result,
        garch_result={"volatility": garch_data["garch_vol"]},
        hmm_result={"regime": hmm_data["regime_label"]},
        risk_result={"risk_regime": signal_data["signal"]},
    )

    # =========================
    # DEBUG
    # =========================

    print("========== MARKET DEBUG ==========")

    print("Current Price:", current_price)
    print("EMA20:", ema20)
    print("EMA50:", ema50)
    print("Momentum:", momentum)
    print("Volatility:", volatility)
    print("Trend:", trend)
    print(
        "Structure Regime:",
        structure_regime,
    )

    print("GARCH VOL:", garch_data["garch_vol"])

    print("VOL REGIME:", garch_data["vol_regime"])

    print("HMM REGIME:", hmm_data["regime_label"])

    print("TREND PROB:", hmm_data["trend_probability"])

    print("CRISIS PROB:", hmm_data["crisis_probability"])

    print("SIGNAL:", signal_data["signal"])

    print("SIGNAL SCORE:", signal_data["signal_score"])

    # =========================
    # API RESPONSE
    # =========================

    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "trend": trend,
        "market_state": market_state,
        "volatility": round(volatility * 100, 2),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
        "momentum": round(momentum, 2),
        "regime": hmm_data["regime_label"],
        "structure_regime": structure_regime,
        # SIGNAL ENGINE
        "signal": signal_data["signal"],
        "signal_score": signal_data["signal_score"],
        "confidence": signal_data["confidence"],
        "bull_probability": signal_data["bull_probability"],
        # GARCH
        "garch_vol": garch_data["garch_vol"],
        "vol_regime": garch_data["vol_regime"],
        "vol_slope": garch_data["vol_slope"],
        # HMM
        "hmm_regime": hmm_data["regime_label"],
        "trend_probability": hmm_data["trend_probability"],
        "crisis_probability": hmm_data["crisis_probability"],
        "mean_revert_probability": hmm_data["mean_revert_probability"],
        # CHART
        "chart_data": chart_data,
        # CROSS-ASSET CORRELATION
        "correlation": correlation_data,
    }


@app.get("/correlation")
def get_correlation():

    return calculate_correlation_intelligence()
