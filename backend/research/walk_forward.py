import pandas as pd
import numpy as np

from research.backtest_engine import run_backtest


def walk_forward_validation(df, train_size=252, test_size=30):

    results = []

    start = 0

    while start + train_size + test_size <= len(df):

        train_df = df.iloc[start : start + train_size]

        test_df = df.iloc[start + train_size : start + train_size + test_size]

        result = run_backtest(test_df)

        results.append(result["metrics"])

        start += test_size

    return results
