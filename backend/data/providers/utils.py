from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def normalize_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    data = df.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    rename_map = {
        "Date": "timestamp",
        "Datetime": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    data = data.reset_index().rename(columns=rename_map)

    for col in REQUIRED_COLUMNS:
        if col not in data.columns:
            if col == "volume":
                data[col] = 0.0
            else:
                raise ValueError(f"Missing required OHLCV column '{col}'")

    data = data[REQUIRED_COLUMNS].copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True, errors="coerce")
    data = data.dropna(subset=["timestamp", "open", "high", "low", "close"])
    data = data.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

    for numeric_col in ["open", "high", "low", "close", "volume"]:
        data[numeric_col] = pd.to_numeric(data[numeric_col], errors="coerce")

    data = data.dropna(subset=["open", "high", "low", "close"])
    data = data.reset_index(drop=True)
    return data


def to_engine_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engine compatibility helper: return index-based OHLCV
    using canonical title-case columns expected by legacy modules.
    """
    if df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])

    out = df.copy()
    out = out.set_index("timestamp")
    out.index = pd.to_datetime(out.index, utc=True)
    out = out.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    return out[["Open", "High", "Low", "Close", "Volume"]]
