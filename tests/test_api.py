"""Unit and integration tests for API services and fallback mechanisms."""

import pytest
from unittest.mock import MagicMock, patch
from marketsentinel.api.client import BaseAPIClient
from marketsentinel.api.coingecko import CoinGeckoService
from marketsentinel.api.binance import BinanceService
from marketsentinel.api.fallbacks import generate_fallback_candles, generate_fallback_ticker
from marketsentinel.core.exceptions import APIConnectionError


def test_fallback_ticker_generation():
    ticker = generate_fallback_ticker("bitcoin", currency="usd")
    assert ticker.symbol == "BTC"
    assert ticker.price > 0
    assert ticker.currency == "USD"
    assert ticker.high_24h >= ticker.price
    assert ticker.low_24h <= ticker.price


def test_fallback_candles_generation():
    candles = generate_fallback_candles("ethereum", days=7)
    assert len(candles) == 7 * 4
    for c in candles:
        assert c.price > 0
        assert c.timestamp is not None


def test_coingecko_symbol_resolution():
    service = CoinGeckoService()
    assert service._resolve_symbol("btc") == "bitcoin"
    assert service._resolve_symbol("eth") == "ethereum"
    assert service._resolve_symbol("sol") == "solana"
    assert service._resolve_symbol("unknown") == "unknown"


@patch("marketsentinel.api.client.requests.Session.get")
def test_base_api_client_retry_and_timeout(mock_get):
    client = BaseAPIClient(base_url="https://api.test.com", timeout=2)
    mock_get.side_effect = TimeoutError("Request timed out")

    with pytest.raises(APIConnectionError) as exc_info:
        client.get("test-endpoint")
    assert "timed out" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


def test_coingecko_fetch_fallback_on_failure():
    service = CoinGeckoService(base_url="https://api.coingecko.com/api/v3")
    with patch.object(service.client.session, "get", side_effect=Exception("Simulated network down")):
        tickers = service.fetch_tickers(["bitcoin", "ethereum"], currency="usd")
        assert len(tickers) == 2
        assert tickers[0].symbol == "BTC"
        assert tickers[1].symbol == "ETH"


def test_binance_ticker_fallback():
    service = BinanceService(base_url="https://api.binance.com/api/v3")
    with patch.object(service.client.session, "get", side_effect=Exception("Simulated exchange down")):
        ticker = service.fetch_ticker("solana")
        assert ticker.symbol == "SOL"
        assert ticker.price > 0
