from typing import Dict


def build_market_state(
    adx_result: Dict,
    garch_result: Dict,
    hmm_result: Dict,
    risk_result: Dict,
) -> Dict:

    adx = adx_result["adx"]

    volatility = garch_result["volatility"]

    regime = hmm_result["regime"]

    # =========================
    # TREND PERSISTENCE
    # =========================

    if adx < 20:
        persistence = "WEAK"

    elif adx < 35:
        persistence = "MODERATE"

    else:
        persistence = "STRONG"

    # =========================
    # VOL REGIME
    # =========================

    if volatility < 0.01:
        vol_regime = "COMPRESSED"

    elif volatility < 0.025:
        vol_regime = "NORMAL"

    else:
        vol_regime = "EXPANDING"

    # =========================
    # TRANSITION RISK
    # =========================

    transition_risk = "LOW"

    if regime == "volatile" and adx < 20:
        transition_risk = "ELEVATED"

    # =========================
    # CONFIDENCE
    # =========================

    confidence = round((min(adx / 50, 1.0) + min(volatility * 20, 1.0)) / 2, 2)

    return {
        "market_regime": regime.upper(),
        "volatility_regime": vol_regime,
        "trend_persistence": persistence,
        "transition_risk": transition_risk,
        "confidence": confidence,
        "adx": round(adx, 2),
        "volatility": round(volatility * 100, 2),
        "risk_state": risk_result["risk_regime"],
    }
