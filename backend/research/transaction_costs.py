# =========================================
# research/transaction_costs.py
# =========================================

import pandas as pd
import numpy as np


def apply_transaction_costs(returns, fee_per_trade=0.001):

    returns = pd.Series(returns)

    adjusted_returns = returns - fee_per_trade

    return adjusted_returns
