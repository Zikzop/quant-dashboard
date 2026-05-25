# =========================================
# QUICK TEST SCRIPT
# create later:
# research/test_research_pipeline.py
# =========================================

import yfinance as yf
import pandas as pd

from research.backtest_engine import run_backtest

from research.walk_forward import walk_forward_validation

from research.monte_carlo import monte_carlo_simulation

symbol = "BTC-USD"

df = yf.download(symbol, period="2y", interval="1d")

df.columns = df.columns.get_level_values(0)

close = df["Close"]

df["EMA20"] = close.ewm(span=20).mean()
df["EMA50"] = close.ewm(span=50).mean()

# =========================
# BACKTEST
# =========================

backtest_results = run_backtest(df)

print("\n========== BACKTEST ==========")

print(backtest_results["metrics"])

# =========================
# WALK FORWARD
# =========================

wf_results = walk_forward_validation(df)

print("\n========== WALK FORWARD ==========")

print(wf_results)

# =========================
# MONTE CARLO
# =========================

mc_results = monte_carlo_simulation(backtest_results["returns"])

print("\n========== MONTE CARLO ==========")

print(mc_results)
