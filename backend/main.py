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

from engines.garch_engine import calculate_garch_volatility

from engines.hmm_regime_engine import HMMRegimeEngine

from engines.signal_engine import calculate_signal_engine

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

    garch_data = calculate_garch_volatility(close)

    # =========================
    # HMM REGIME ENGINE
    # =========================

    hmm_data = hmm_engine.classify_regimes(df)

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
    # CHART DATA
    # =========================

    adx_latest = adx_engine.compute_latest(df)

    adx_result = adx_result_to_dict(adx_latest)

    chart_data = []

    for index, row in df.tail(30).iterrows():

        chart_data.append(
            {
                "time":
                    index.strftime("%Y-%m-%d"),

                "open":
                    round(float(row["Open"]), 2),

                "high":
                    round(float(row["High"]), 2),

                "low":
                    round(float(row["Low"]), 2),

                "close":
                    round(float(row["Close"]), 2),

                "ema20":
                    round(float(row["EMA20"]), 2),

                "ema50":
                    round(float(row["EMA50"]), 2),

                # =====================
                # REAL INTELLIGENCE
                # =====================

                "adx":
                    round(
                        float(adx_result["adx"]),
                        2
                    ),

                "direction":
                    adx_result["direction"],

                "trend_strength":
                    adx_result["strength"],

                "hmm_regime":
                    hmm_data["regime_label"],

                "trend_probability":
                    round(
                        float(
                            hmm_data[
                                "trend_probability"
                            ]
                        ),
                        4
                    ),

                "crisis_probability":
                    round(
                        float(
                            hmm_data[
                                "crisis_probability"
                            ]
                        ),
                        4
                    ),

                "garch_vol":
                    round(
                        float(
                            garch_data[
                                "garch_vol"
                            ]
                        ),
                        4
                    ),

                "vol_regime":
                    garch_data[
                        "vol_regime"
                    ],
            }
        )

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
    print("Regime:", regime)

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
    }
