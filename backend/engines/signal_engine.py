import numpy as np


def calculate_signal_engine(trend, momentum, volatility, hmm_data, garch_data):

    signal_score = 0

    # TREND COMPONENT
    if trend == "BULLISH":
        signal_score += 25

    elif trend == "BEARISH":
        signal_score -= 25

    # VOL-ADJUSTED MOMENTUM
    vol_adjusted_momentum = (momentum / (volatility + 1e-6)) * 100

    signal_score += vol_adjusted_momentum

    # HMM TREND PROBABILITY
    signal_score += hmm_data["trend_probability"] * 0.3

    # CRISIS PENALTY
    signal_score -= hmm_data["crisis_probability"] * 0.4

    # GARCH VOLATILITY EXPANSION
    if garch_data["vol_regime"] == "EXPANDING_VOL":

        if trend == "BULLISH":
            signal_score += 10

        elif trend == "BEARISH":
            signal_score -= 10

    # FINAL SIGNAL CLASSIFICATION
    signal = "NEUTRAL"

    if signal_score >= 60:
        signal = "STRONG BUY"

    elif signal_score >= 25:
        signal = "BUY"

    elif signal_score <= -60:
        signal = "AVOID"

    elif signal_score <= -25:
        signal = "SELL"

    confidence = min(max(abs(signal_score), 5), 95)

    bull_probability = min(max(50 + signal_score * 0.5, 1), 99)

    return {
        "signal": signal,
        "signal_score": round(signal_score, 2),
        "confidence": round(confidence, 2),
        "bull_probability": round(bull_probability, 2),
    }
