#!/usr/bin/env python3
"""
Market data orchestration pipeline.

Flow:
    collect → validate → normalize → save clean parquet
         → generate features → save features parquet
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from config.data_paths import get_data_paths
from ingestion.yfinance_collector import (
    DEFAULT_SYMBOL,
    YFinanceCollector,
    YFinanceCollectorConfig,
)
from pipelines.feature_pipeline import FeaturePipeline
from pipelines.normalization_pipeline import NormalizationPipeline
from storage.parquet_handler import ParquetHandler
from validation.ohlcv_validator import OHLCVValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_data_pipeline")


def run_pipeline(
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = "1d",
    period: str = "2y",
    fail_on_validation_errors: bool = True,
) -> dict:
    paths = get_data_paths()
    paths.ensure_all()

    collector = YFinanceCollector(
        YFinanceCollectorConfig(
            symbol=symbol,
            interval=interval,
            period=period,
        )
    )
    raw_df = collector.collect()

    normalizer = NormalizationPipeline()
    normalized = normalizer.run(raw_df)

    validator = OHLCVValidator(drop_invalid_rows=True)
    clean_df, report = validator.validate(
        normalized,
        symbol=symbol,
        interval=interval,
    )

    if fail_on_validation_errors and not report.passed:
        raise ValueError(
            f"OHLCV validation failed for {symbol}:\n{report.summary()}"
        )

    clean_handler = ParquetHandler.for_tier("clean", paths=paths)
    normalized_handler = ParquetHandler.for_tier("normalized", paths=paths)
    features_handler = ParquetHandler.for_tier("features", paths=paths)

    clean_export = normalizer.to_timestamp_column(clean_df)
    clean_path = clean_handler.save(clean_export, symbol, interval, index=False)
    normalized_handler.save(clean_export, symbol, interval, index=False)

    feature_pipeline = FeaturePipeline()
    features_df = feature_pipeline.run(clean_df)
    features_export = normalizer.to_timestamp_column(features_df)
    features_path = features_handler.save(
        features_export, symbol, interval, index=False
    )

    result = {
        "symbol": symbol,
        "interval": interval,
        "rows": len(clean_df),
        "validation_passed": report.passed,
        "clean_path": str(clean_path),
        "features_path": str(features_path),
        "issues": [
            {"code": i.code, "severity": i.severity, "count": i.count}
            for i in report.issues
        ],
    }
    logger.info("Pipeline complete: %s", result)
    return result


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Institutional market data pipeline")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--period", default="2y")
    parser.add_argument(
        "--allow-validation-warnings",
        action="store_true",
        help="Do not abort when validation records correctable errors",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    try:
        run_pipeline(
            symbol=args.symbol,
            interval=args.interval,
            period=args.period,
            fail_on_validation_errors=not args.allow_validation_warnings,
        )
        return 0
    except Exception:
        logger.exception("Pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
