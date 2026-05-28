from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal

AssetClass = Literal["crypto", "fx", "future", "index"]


@dataclass(frozen=True)
class AssetDefinition:
    asset_id: str
    provider_symbol: str
    asset_class: AssetClass
    quote_currency: str
    session: str
    timezone: str


ASSET_REGISTRY: Dict[str, AssetDefinition] = {
    "BTC": AssetDefinition(
        asset_id="BTC",
        provider_symbol="BTC-USD",
        asset_class="crypto",
        quote_currency="USD",
        session="24x7",
        timezone="UTC",
    ),
    "GOLD": AssetDefinition(
        asset_id="GOLD",
        provider_symbol="GC=F",
        asset_class="future",
        quote_currency="USD",
        session="CME",
        timezone="America/New_York",
    ),
    "ES": AssetDefinition(
        asset_id="ES",
        provider_symbol="ES=F",
        asset_class="future",
        quote_currency="USD",
        session="CME",
        timezone="America/New_York",
    ),
    "NQ": AssetDefinition(
        asset_id="NQ",
        provider_symbol="NQ=F",
        asset_class="future",
        quote_currency="USD",
        session="CME",
        timezone="America/New_York",
    ),
    "DXY": AssetDefinition(
        asset_id="DXY",
        provider_symbol="DX-Y.NYB",
        asset_class="index",
        quote_currency="USD",
        session="ICE",
        timezone="America/New_York",
    ),
}


def normalize_asset_id(asset_id: str | None) -> str:
    if not asset_id:
        return "BTC"
    normalized = asset_id.strip().upper()
    if normalized not in ASSET_REGISTRY:
        supported = ", ".join(sorted(ASSET_REGISTRY.keys()))
        raise ValueError(f"Unsupported asset_id '{asset_id}'. Supported: {supported}")
    return normalized


def get_asset_definition(asset_id: str) -> AssetDefinition:
    normalized = normalize_asset_id(asset_id)
    return ASSET_REGISTRY[normalized]


def resolve_symbol(symbol_or_id: str | None) -> AssetDefinition:
    """Accept either a registry asset id (e.g. ``GOLD``) or a provider symbol
    (e.g. ``GC=F``) and return the canonical asset definition.

    Lets the API accept ``?symbol=GOLD`` or ``?symbol=BTC-USD`` interchangeably,
    which keeps the contract forgiving for clients while staying centralized.
    """
    if not symbol_or_id:
        return ASSET_REGISTRY["BTC"]
    candidate = symbol_or_id.strip()
    upper = candidate.upper()
    if upper in ASSET_REGISTRY:
        return ASSET_REGISTRY[upper]
    for definition in ASSET_REGISTRY.values():
        if definition.provider_symbol.upper() == upper:
            return definition
    supported = ", ".join(sorted(ASSET_REGISTRY.keys()))
    raise ValueError(
        f"Unsupported symbol '{symbol_or_id}'. Supported asset ids: {supported}"
    )


def asset_metadata(definition: AssetDefinition) -> dict:
    """JSON-serializable metadata for the /assets API and frontend selectors."""
    from assets.sessions import get_session

    session = get_session(definition.session)
    return {
        "asset_id": definition.asset_id,
        "provider_symbol": definition.provider_symbol,
        "asset_class": definition.asset_class,
        "quote_currency": definition.quote_currency,
        "session": {
            "id": session.session_id,
            "description": session.description,
            "timezone": session.timezone,
            "is_24x7": session.is_24x7,
            "rth_open": session.rth_open,
            "rth_close": session.rth_close,
            "has_overnight_gap": session.has_overnight_gap,
        },
        "timezone": definition.timezone,
    }


def list_asset_metadata() -> list[dict]:
    return [asset_metadata(d) for d in ASSET_REGISTRY.values()]
