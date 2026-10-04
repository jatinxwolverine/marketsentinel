"""CoinGecko API service integration with automatic resilience and rate-limit fallbacks."""

from __future__ import annotations

import time
from marketsentinel.api.client import BaseAPIClient
from marketsentinel.api.fallbacks import generate_fallback_candles, generate_fallback_ticker
from marketsentinel.core.exceptions import APIConnectionError
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.cleaner import DataCleaner
from marketsentinel.processing.models import CandlePoint, TickerData

logger = get_logger("marketsentinel.api.coingecko")

# Standard symbol-to-id mapping for convenience
COIN_MAPPINGS: dict[str, str] = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "xrp": "ripple",
    "doge": "dogecoin",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "link": "chainlink",
}


class CoinGeckoService:
    """Service wrapper for interacting with CoinGecko REST endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.coingecko.com/api/v3",
        timeout: int = 6,
        api_key: str | None = None,
    ) -> None:
        self.client = BaseAPIClient(base_url=base_url, timeout=timeout)
        self.api_key = api_key
        if self.api_key:
            self.client.session.headers.update({"x-cg-demo-api-key": self.api_key})

    def _resolve_symbol(self, symbol: str) -> str:
        clean = symbol.lower().strip()
        return COIN_MAPPINGS.get(clean, clean)

    def fetch_tickers(
        self, symbols: list[str], currency: str = "usd"
    ) -> list[TickerData]:
        """Fetches live market snapshot data for the specified coin identifiers."""
        resolved = [self._resolve_symbol(s) for s in symbols]
        ids_param = ",".join(resolved)
        curr = currency.lower()

        tickers: list[TickerData] = []
        try:
            endpoint = "simple/price"
            params = {
                "ids": ids_param,
                "vs_currencies": curr,
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_market_cap": "true",
            }
            data = self.client.get(endpoint, params=params)

            if isinstance(data, dict):
                for coin_id in resolved:
                    if coin_id in data and curr in data[coin_id]:
                        cleaned = DataCleaner.clean_ticker(
                            data[coin_id], symbol=coin_id, currency=curr
                        )
                        tickers.append(cleaned)
                    else:
                        logger.warning(
                            f"Missing data for {coin_id} in API response. Using fallback."
                        )
                        tickers.append(generate_fallback_ticker(coin_id, currency=curr))
            else:
                raise APIConnectionError("Unexpected response structure from CoinGecko")

        except Exception as e:
            logger.warning(
                f"CoinGecko live fetch encountered: {e}. Activating high-resilience fallback buffer."
            )
            tickers = [
                generate_fallback_ticker(coin_id, currency=curr)
                for coin_id in resolved
            ]

        return tickers

    def fetch_historical_candles(
        self, symbol: str, days: int = 14, currency: str = "usd"
    ) -> list[CandlePoint]:
        """Fetches historical price timeseries for charting and technical indicators."""
        coin_id = self._resolve_symbol(symbol)
        curr = currency.lower()

        try:
            endpoint = f"coins/{coin_id}/market_chart"
            params: dict[str, str] = {
                "vs_currency": curr,
                "days": str(days),
            }
            if days > 90:
                params["interval"] = "daily"
            data = self.client.get(endpoint, params=params)

            if isinstance(data, dict) and "prices" in data:
                raw_prices = data["prices"]
                candles = DataCleaner.clean_timeseries(raw_prices)
                if candles:
                    return candles

            logger.warning(
                f"Insufficient historical data for {coin_id}. Engaging fallback series."
            )
            return generate_fallback_candles(coin_id, days=days)

        except Exception as e:
            logger.warning(
                f"Historical fetch failed for {coin_id} ({e}). Generating fallback series."
            )
            return generate_fallback_candles(coin_id, days=days)

    def close(self) -> None:
        self.client.close()
