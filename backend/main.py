import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

# ─────────────────────────────────────────────────────────────────────────────
# MULTI-TIMEFRAME CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

VALID_TIMEFRAMES = {"1m", "5m", "15m", "1H", "4H", "1D"}

TF_CONFIG = {
    "1m":  {"yf_interval": "1m",  "yf_period": "7d",   "chart_bars": 300, "bars_per_year": 525960},
    "5m":  {"yf_interval": "5m",  "yf_period": "60d",  "chart_bars": 200, "bars_per_year": 105192},
    "15m": {"yf_interval": "15m", "yf_period": "60d",  "chart_bars": 150, "bars_per_year": 35064},
    "1H":  {"yf_interval": "1h",  "yf_period": "730d", "chart_bars": 120, "bars_per_year": 8766},
    "4H":  {"yf_interval": "1h",  "yf_period": "730d", "chart_bars": 120, "bars_per_year": 2190, "resample": "4h"},
    "1D":  {"yf_interval": "1d",  "yf_period": "2y",   "chart_bars": 120, "bars_per_year": 365},
}

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


# ─────────────────────────────────────────────────────────────────────────────
# PER-TIMEFRAME ENDPOINT — real independent OHLCV + indicators per TF
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/market/timeframe/{tf}")
def get_market_timeframe(tf: str):
    if tf not in VALID_TIMEFRAMES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid timeframe: {tf}. Valid: {sorted(VALID_TIMEFRAMES)}"},
        )

    try:
        config = TF_CONFIG[tf]
        symbol = "BTC-USD"

        df = yf.download(
            symbol,
            period=config["yf_period"],
            interval=config["yf_interval"],
        )

        if df.empty:
            return JSONResponse(
                status_code=500,
                content={"error": f"No data returned for {symbol} at {tf}"},
            )

        df.columns = df.columns.get_level_values(0)

        # 4H: resample from 1h candles
        if "resample" in config:
            df = (
                df.resample(config["resample"])
                .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
                .dropna()
            )

        if len(df) < 30:
            return JSONResponse(
                status_code=500,
                content={"error": f"Insufficient data for {tf}: only {len(df)} bars"},
            )

        close = df["Close"].squeeze()

        # ========================= TECHNICAL STRUCTURE =========================

        df["EMA20"] = close.ewm(span=20).mean()
        df["EMA50"] = close.ewm(span=50).mean()

        returns = close.pct_change()
        bars_per_year = config["bars_per_year"]
        volatility = returns.std() * np.sqrt(bars_per_year)

        current_price = float(close.iloc[-1])
        ema20 = float(df["EMA20"].iloc[-1])
        ema50 = float(df["EMA50"].iloc[-1])

        # ========================= TREND ENGINE =========================

        trend = "RANGING"
        if current_price > ema20 and ema20 > ema50:
            trend = "BULLISH"
        elif current_price < ema20 and ema20 < ema50:
            trend = "BEARISH"

        # ========================= MOMENTUM =========================

        lookback = min(20, len(close) - 1)
        momentum = ((current_price / float(close.iloc[-lookback - 1])) - 1) * 100

        # ========================= ADX ENGINE =========================

        adx_history = adx_engine.compute_per_bar_series(df)
        adx_latest = adx_engine.compute_latest(df)
        adx_result = adx_result_to_dict(adx_latest)

        # ========================= GARCH ENGINE =========================

        garch_close = close.iloc[-2000:] if len(close) > 2000 else close
        try:
            garch_history = calculate_garch_volatility_series(garch_close)
            garch_latest = garch_history.dropna(subset=["garch_vol"]).iloc[-1]
            garch_data = {
                "garch_vol": round(float(garch_latest["garch_vol"]), 2),
                "vol_regime": str(garch_latest["vol_regime"]),
                "vol_slope": round(float(garch_latest["vol_slope"]), 2)
                if not pd.isna(garch_latest["vol_slope"])
                else 0.0,
            }
        except Exception:
            garch_history = pd.DataFrame(
                columns=["garch_vol", "vol_slope", "vol_regime"],
                index=close.index,
            )
            garch_data = {"garch_vol": 0.0, "vol_regime": "UNKNOWN", "vol_slope": 0.0}

        # ========================= HMM ENGINE (single-fit) =========================

        hmm_df = df.iloc[-2000:] if len(df) > 2000 else df
        try:
            hmm_history = hmm_engine.compute_single_fit_regimes(hmm_df)
            hmm_data = hmm_engine.classify_regimes(hmm_df)
        except Exception:
            hmm_history = pd.DataFrame()
            hmm_data = {
                "regime_label": "UNKNOWN",
                "trend_probability": 0.0,
                "crisis_probability": 0.0,
                "mean_revert_probability": 0.0,
            }

        # ========================= SIGNAL ENGINE =========================

        signal_data = calculate_signal_engine(
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            hmm_data=hmm_data,
            garch_data=garch_data,
        )

        # ========================= MARKET STATE =========================

        market_state = build_market_state(
            adx_result=adx_result,
            garch_result={"volatility": garch_data["garch_vol"]},
            hmm_result={"regime": hmm_data["regime_label"]},
            risk_result={"risk_regime": signal_data["signal"]},
        )

        # ========================= STRUCTURE REGIME =========================

        structure_regime = "RANGING"
        if garch_data["vol_regime"] == "EXPANDING_VOL":
            structure_regime = "VOLATILE"
        if trend == "BULLISH" and momentum > 5:
            structure_regime = "TRENDING_BULL"
        elif trend == "BEARISH" and momentum < -5:
            structure_regime = "TRENDING_BEAR"

        # ========================= CHART DATA =========================

        chart_bars = min(config["chart_bars"], len(df))
        is_intraday = tf != "1D"
        chart_data = []

        for index, row in df.tail(chart_bars).iterrows():
            bar = {
                "time": int(index.timestamp()) if is_intraday else index.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "ema20": round(float(row["EMA20"]), 2),
                "ema50": round(float(row["EMA50"]), 2),
            }

            if index in adx_history.index:
                adx_row = adx_history.loc[index]
                if not pd.isna(adx_row.get("adx")):
                    bar["adx"] = round(float(adx_row["adx"]), 2)
                    bar["plus_di"] = round(float(adx_row["plus_di"]), 2)
                    bar["minus_di"] = round(float(adx_row["minus_di"]), 2)
                    bar["direction"] = adx_row["direction"]
                    bar["trend_strength"] = adx_row["trend_strength"]

            if index in garch_history.index:
                garch_row = garch_history.loc[index]
                if not pd.isna(garch_row.get("garch_vol")):
                    bar["garch_vol"] = round(float(garch_row["garch_vol"]), 4)
                    bar["vol_regime"] = str(garch_row["vol_regime"])

            if not hmm_history.empty and index in hmm_history.index:
                hmm_row = hmm_history.loc[index]
                if hmm_row.get("hmm_regime") is not None and not (
                    isinstance(hmm_row.get("hmm_regime"), float)
                    and pd.isna(hmm_row.get("hmm_regime"))
                ):
                    bar["hmm_regime"] = str(hmm_row["hmm_regime"])
                    bar["mean_revert_probability"] = round(float(hmm_row["mean_revert_probability"]), 4)
                    bar["trend_probability"] = round(float(hmm_row["trend_probability"]), 4)
                    bar["crisis_probability"] = round(float(hmm_row["crisis_probability"]), 4)

            chart_data.append(bar)

        # ========================= CORRELATION (1D only) =========================

        correlation_data = None
        if tf == "1D":
            try:
                correlation_data = calculate_correlation_intelligence(
                    regime_label=hmm_data["regime_label"],
                )
            except Exception:
                correlation_data = None

        # ========================= RESPONSE =========================

        print(f"========== {tf} TIMEFRAME DEBUG ==========")
        print(f"Bars downloaded: {len(df)}, Chart bars: {len(chart_data)}")
        print(f"Price: {current_price}, Trend: {trend}, ADX: {adx_result['adx']}")
        print(f"HMM: {hmm_data['regime_label']}, GARCH: {garch_data['vol_regime']}")

        return {
            "symbol": symbol,
            "timeframe": tf,
            "price": round(current_price, 2),
            "trend": trend,
            "market_state": market_state,
            "volatility": round(volatility * 100, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "momentum": round(momentum, 2),
            "regime": hmm_data["regime_label"],
            "structure_regime": structure_regime,
            "signal": signal_data["signal"],
            "signal_score": signal_data["signal_score"],
            "confidence": signal_data["confidence"],
            "bull_probability": signal_data["bull_probability"],
            "garch_vol": garch_data["garch_vol"],
            "vol_regime": garch_data["vol_regime"],
            "vol_slope": garch_data["vol_slope"],
            "hmm_regime": hmm_data["regime_label"],
            "trend_probability": hmm_data["trend_probability"],
            "crisis_probability": hmm_data["crisis_probability"],
            "mean_revert_probability": hmm_data["mean_revert_probability"],
            "chart_data": chart_data,
            "correlation": correlation_data,
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
