"""Binance public market data service integration."""

from __future__ import annotations

from datetime import datetime, timezone
from marketsentinel.api.client import BaseAPIClient
from marketsentinel.api.fallbacks import generate_fallback_ticker
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.models import TickerData

logger = get_logger("marketsentinel.api.binance")

BINANCE_SYMBOL_MAP: dict[str, str] = {
    "bitcoin": "BTCUSDT",
    "btc": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "eth": "ETHUSDT",
    "solana": "SOLUSDT",
    "sol": "SOLUSDT",
    "cardano": "ADAUSDT",
    "ada": "ADAUSDT",
    "ripple": "XRPUSDT",
    "xrp": "XRPUSDT",
}


class BinanceService:
    """Service for querying Binance public exchange endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.binance.com/api/v3",
        timeout: int = 10,
    ) -> None:
        self.client = BaseAPIClient(base_url=base_url, timeout=timeout)

    def fetch_ticker(self, symbol: str) -> TickerData:
        """Fetches 24hr ticker price change statistics for a symbol."""
        binance_pair = BINANCE_SYMBOL_MAP.get(symbol.lower(), f"{symbol.upper()}USDT")
        try:
            data = self.client.get("ticker/24hr", params={"symbol": binance_pair})
            if isinstance(data, dict) and "lastPrice" in data:
                price = float(data.get("lastPrice", 0.0))
                change_pct = float(data.get("priceChangePercent", 0.0))
                volume = float(data.get("quoteVolume", 0.0))
                high = float(data.get("highPrice", price))
                low = float(data.get("lowPrice", price))

                return TickerData(
                    symbol=symbol.upper(),
                    name=symbol.capitalize(),
                    price=price,
                    currency="USD",
                    change_24h_pct=change_pct,
                    volume_24h=volume,
                    high_24h=high,
                    low_24h=low,
                    market_cap=volume * 20.0,
                    last_updated=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.warning(f"Binance fetch failed for {binance_pair}: {e}. Using fallback.")

        return generate_fallback_ticker(symbol, currency="usd")

    def close(self) -> None:
        self.client.close()
