from __future__ import annotations

import os
from typing import Dict

from data.providers.base import MarketDataProvider
from data.providers.databento_provider import DatabentoProvider
from data.providers.mock_provider import MockProvider
from data.providers.yahoo_provider import YahooProvider


_PROVIDER_FACTORIES: Dict[str, type] = {
    "yahoo": YahooProvider,
    "mock": MockProvider,
    "databento": DatabentoProvider,
}


def get_market_data_provider() -> MarketDataProvider:
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "yahoo").strip().lower()
    provider_cls = _PROVIDER_FACTORIES.get(provider_name)
    if provider_cls is None:
        supported = ", ".join(sorted(_PROVIDER_FACTORIES.keys()))
        raise ValueError(
            f"Unsupported MARKET_DATA_PROVIDER '{provider_name}'. Supported: {supported}"
        )
    return provider_cls()
