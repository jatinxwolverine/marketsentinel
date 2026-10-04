"""API clients and market data feeds."""

from marketsentinel.api.client import BaseAPIClient
from marketsentinel.api.coingecko import CoinGeckoService
from marketsentinel.api.binance import BinanceService
from marketsentinel.api.fallbacks import generate_fallback_ticker, generate_fallback_candles

__all__ = [
    "BaseAPIClient",
    "CoinGeckoService",
    "BinanceService",
    "generate_fallback_ticker",
    "generate_fallback_candles",
]
