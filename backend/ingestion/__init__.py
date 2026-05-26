"""Market data ingestion adapters."""

from ingestion.yfinance_collector import YFinanceCollector, YFinanceCollectorConfig

__all__ = ["YFinanceCollector", "YFinanceCollectorConfig"]
