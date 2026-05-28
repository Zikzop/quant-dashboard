"""
OHLCV integrity validation for institutional market data tiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

IssueSeverity = Literal["error", "warning"]

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass
class ValidationIssue:
    code: str
    severity: IssueSeverity
    message: str
    count: int = 0


@dataclass
class OHLCVValidationReport:
    symbol: str
    interval: str
    input_rows: int
    output_rows: int
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "error":
            self.passed = False

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"OHLCV validation [{status}] symbol={self.symbol} "
            f"interval={self.interval} rows={self.input_rows}->{self.output_rows}",
        ]
        for issue in self.issues:
            lines.append(
                f"  [{issue.severity.upper()}] {issue.code}: "
                f"{issue.message} (n={issue.count})"
            )
        return "\n".join(lines)


class OHLCVValidator:
    """
    Validate and clean normalized OHLCV frames.

    Never silently drops corrupt rows without recording an issue.
    """

    def __init__(self, *, drop_invalid_rows: bool = True) -> None:
        self.drop_invalid_rows = drop_invalid_rows

    def validate(
        self,
        df: pd.DataFrame,
        *,
        symbol: str = "UNKNOWN",
        interval: str = "1d",
    ) -> tuple[pd.DataFrame, OHLCVValidationReport]:
        report = OHLCVValidationReport(
            symbol=symbol,
            interval=interval,
            input_rows=len(df),
            output_rows=0,
            passed=True,
        )

        if df.empty:
            report.add(
                ValidationIssue(
                    code="EMPTY_FRAME",
                    severity="error",
                    message="Input dataframe is empty",
                )
            )
            report.output_rows = 0
            logger.error(report.summary())
            return df.copy(), report

        # Establish the DatetimeIndex *before* selecting OHLCV columns — otherwise
        # the timestamp column is dropped and the frame keeps a RangeIndex (0..n),
        # which serializes to chart time=0 and breaks lightweight-charts.
        working = self._ensure_datetime_index(df)
        working = self._ensure_normalized_columns(working)

        duplicate_mask = working.index.duplicated(keep=False)
        if duplicate_mask.any():
            n_dup = int(duplicate_mask.sum())
            report.add(
                ValidationIssue(
                    code="DUPLICATE_TIMESTAMPS",
                    severity="error",
                    message="Duplicate timestamps detected",
                    count=n_dup,
                )
            )
            working = working[~working.index.duplicated(keep="last")]

        if not working.index.is_monotonic_increasing:
            report.add(
                ValidationIssue(
                    code="NON_MONOTONIC_TIMESTAMPS",
                    severity="error",
                    message="Timestamps are not strictly monotonic increasing",
                )
            )
            working = working.sort_index()

        nan_ohlc = working[list(OHLCV_COLUMNS[:4])].isna().any(axis=1)
        if nan_ohlc.any():
            n_nan = int(nan_ohlc.sum())
            report.add(
                ValidationIssue(
                    code="NAN_OHLC",
                    severity="error",
                    message="NaN values in OHLC columns",
                    count=n_nan,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~nan_ohlc]

        neg_volume = working["volume"] < 0
        if neg_volume.any():
            n_neg = int(neg_volume.sum())
            report.add(
                ValidationIssue(
                    code="NEGATIVE_VOLUME",
                    severity="error",
                    message="Volume < 0",
                    count=n_neg,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~neg_volume]

        invalid_hl = working["high"] < working["low"]
        if invalid_hl.any():
            n_bad = int(invalid_hl.sum())
            report.add(
                ValidationIssue(
                    code="HIGH_BELOW_LOW",
                    severity="error",
                    message="High < Low",
                    count=n_bad,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~invalid_hl]

        invalid_high = (working["high"] < working["open"]) | (
            working["high"] < working["close"]
        )
        if invalid_high.any():
            n_bad = int(invalid_high.sum())
            report.add(
                ValidationIssue(
                    code="HIGH_BELOW_OPEN_CLOSE",
                    severity="error",
                    message="High < Open or High < Close",
                    count=n_bad,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~invalid_high]

        invalid_low = (working["open"] < working["low"]) | (
            working["close"] < working["low"]
        )
        if invalid_low.any():
            n_bad = int(invalid_low.sum())
            report.add(
                ValidationIssue(
                    code="LOW_ABOVE_OPEN_CLOSE",
                    severity="error",
                    message="Open or Close < Low",
                    count=n_bad,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~invalid_low]

        non_positive = (working["open"] <= 0) | (working["high"] <= 0) | (
            working["low"] <= 0
        ) | (working["close"] <= 0)
        if non_positive.any():
            n_bad = int(non_positive.sum())
            report.add(
                ValidationIssue(
                    code="NON_POSITIVE_PRICE",
                    severity="error",
                    message="Non-positive OHLC price",
                    count=n_bad,
                )
            )
            if self.drop_invalid_rows:
                working = working.loc[~non_positive]

        report.output_rows = len(working)
        if report.passed:
            logger.info(
                "OHLCV validation passed symbol=%s rows=%d",
                symbol,
                report.output_rows,
            )
        else:
            logger.warning(report.summary())

        return working, report

    @staticmethod
    def _ensure_normalized_columns(df: pd.DataFrame) -> pd.DataFrame:
        rename = {c: c.lower().strip() for c in df.columns}
        out = df.rename(columns=rename)
        missing = set(OHLCV_COLUMNS) - set(out.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        return out[list(OHLCV_COLUMNS)].copy()

    @staticmethod
    def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
        if "timestamp" in df.columns:
            out = df.set_index("timestamp")
        elif isinstance(df.index, pd.DatetimeIndex):
            out = df.copy()
        else:
            raise ValueError("OHLCV frame has no timestamp column or DatetimeIndex")
        out.index = pd.to_datetime(out.index, utc=True, errors="coerce")
        out = out[~out.index.isna()]
        return out
