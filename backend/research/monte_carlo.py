# =========================================
# research/monte_carlo.py
# =========================================

import numpy as np
import pandas as pd


def monte_carlo_simulation(returns, simulations=1000):

    returns = np.array(returns)

    ending_values = []

    for _ in range(simulations):

        simulated_returns = np.random.choice(returns, size=len(returns), replace=True)

        equity_curve = (1 + simulated_returns).cumprod()

        ending_values.append(equity_curve[-1])

    return {
        "mean_ending_value": round(float(np.mean(ending_values)), 2),
        "worst_case": round(float(np.percentile(ending_values, 5)), 2),
        "best_case": round(float(np.percentile(ending_values, 95)), 2),
    }
