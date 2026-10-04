"""High-fidelity fallback market data generator for offline resilience and rate-limit buffering."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from marketsentinel.processing.models import CandlePoint, TickerData

# Realistic baseline seed prices (USD)
BASE_MARKET_SNAPSHOTS: dict[str, dict] = {
    "bitcoin": {
        "symbol": "BTC",
        "name": "Bitcoin",
        "price": 64250.0,
        "change_24h_pct": 2.45,
        "volume_24h": 28_400_000_000.0,
        "market_cap": 1_260_000_000_000.0,
    },
    "ethereum": {
        "symbol": "ETH",
        "name": "Ethereum",
        "price": 3480.0,
        "change_24h_pct": -1.15,
        "volume_24h": 14_200_000_000.0,
        "market_cap": 418_000_000_000.0,
    },
    "solana": {
        "symbol": "SOL",
        "name": "Solana",
        "price": 148.5,
        "change_24h_pct": 5.82,
        "volume_24h": 3_900_000_000.0,
        "market_cap": 68_000_000_000.0,
    },
    "cardano": {
        "symbol": "ADA",
        "name": "Cardano",
        "price": 0.42,
        "change_24h_pct": -0.85,
        "volume_24h": 410_000_000.0,
        "market_cap": 15_100_000_000.0,
    },
    "ripple": {
        "symbol": "XRP",
        "name": "XRP",
        "price": 0.58,
        "change_24h_pct": 3.12,
        "volume_24h": 1_250_000_000.0,
        "market_cap": 32_800_000_000.0,
    },
}


def generate_fallback_ticker(symbol_id: str, currency: str = "usd") -> TickerData:
    """Generates realistic market ticker data with slight jitter."""
    key = symbol_id.lower()
    base = BASE_MARKET_SNAPSHOTS.get(
        key,
        {
            "symbol": key.upper()[:4],
            "name": key.capitalize(),
            "price": 100.0,
            "change_24h_pct": 1.2,
            "volume_24h": 50_000_000.0,
            "market_cap": 1_000_000_000.0,
        },
    )

    jitter = random.uniform(-0.015, 0.015)
    price = round(base["price"] * (1.0 + jitter), 2 if base["price"] > 1 else 4)
    change = round(base["change_24h_pct"] + random.uniform(-0.3, 0.3), 2)
    high = round(price * 1.035, 2 if price > 1 else 4)
    low = round(price * 0.965, 2 if price > 1 else 4)

    return TickerData(
        symbol=base["symbol"],
        name=base["name"],
        price=price,
        currency=currency.upper(),
        change_24h_pct=change,
        volume_24h=base["volume_24h"],
        high_24h=high,
        low_24h=low,
        market_cap=base["market_cap"],
        last_updated=datetime.now(timezone.utc),
    )


def generate_fallback_candles(symbol_id: str, days: int = 14) -> list[CandlePoint]:
    """Generates realistic synthetic candle series for technical indicator analysis."""
    key = symbol_id.lower()
    base_price = BASE_MARKET_SNAPSHOTS.get(key, {}).get("price", 100.0)

    now = datetime.now(timezone.utc)
    points: list[CandlePoint] = []
    current = base_price * 0.92

    total_points = days * 4  # 6-hour interval steps
    step_hours = 6

    for i in range(total_points):
        ts = now - timedelta(hours=(total_points - i) * step_hours)
        fluctuation = random.uniform(-0.02, 0.025)
        current = max(0.001, current * (1.0 + fluctuation))
        points.append(CandlePoint(timestamp=ts, price=round(current, 4)))

    return points
