"""
Canonical OHLCV schema for normalized market data tiers.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OHLCVBar(BaseModel):
    """Single validated OHLCV observation."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_aware_or_naive_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is not None and value.utcoffset() is None:
            raise ValueError("timestamp must be UTC when timezone-aware")
        return value


class OHLCVSchema(BaseModel):
    """Batch schema wrapper for pipeline validation hooks."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    interval: str
    bars: List[OHLCVBar]

    @field_validator("symbol")
    @classmethod
    def symbol_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("symbol must be non-empty")
        return value.strip()
