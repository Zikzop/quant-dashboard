import numpy as np
import pandas as pd


def calculate_performance_metrics(returns, risk_free_rate=0.02):

    returns = pd.Series(returns).dropna()

    # =========================
    # TOTAL RETURN
    # =========================

    total_return = ((1 + returns).prod() - 1) * 100

    # =========================
    # ANNUALIZED RETURN
    # =========================

    annual_return = (returns.mean() * 252) * 100

    # =========================
    # VOLATILITY
    # =========================

    volatility = (returns.std() * np.sqrt(252)) * 100

    # =========================
    # SHARPE RATIO
    # =========================

    excess_returns = returns - risk_free_rate / 252

    sharpe_ratio = (excess_returns.mean() / (returns.std() + 1e-9)) * np.sqrt(252)

    # =========================
    # SORTINO RATIO
    # =========================

    downside_returns = returns[returns < 0]

    downside_std = downside_returns.std() + 1e-9

    sortino_ratio = (excess_returns.mean() / downside_std) * np.sqrt(252)

    # =========================
    # MAX DRAWDOWN
    # =========================

    cumulative = (1 + returns).cumprod()

    running_max = cumulative.cummax()

    drawdown = (cumulative - running_max) / running_max

    max_drawdown = drawdown.min() * 100

    # =========================
    # CALMAR RATIO
    # =========================

    calmar_ratio = annual_return / (abs(max_drawdown) + 1e-9)

    # =========================
    # WIN RATE
    # =========================

    win_rate = (returns > 0).mean() * 100

    # =========================
    # SKEWNESS
    # =========================

    skewness = returns.skew()

    # =========================
    # KURTOSIS
    # =========================

    kurtosis = returns.kurtosis()

    return {
        "total_return": round(float(total_return), 2),
        "annual_return": round(float(annual_return), 2),
        "volatility": round(float(volatility), 2),
        "sharpe_ratio": round(float(sharpe_ratio), 2),
        "sortino_ratio": round(float(sortino_ratio), 2),
        "max_drawdown": round(float(max_drawdown), 2),
        "calmar_ratio": round(float(calmar_ratio), 2),
        "win_rate": round(float(win_rate), 2),
        "skewness": round(float(skewness), 2),
        "kurtosis": round(float(kurtosis), 2),
    }
