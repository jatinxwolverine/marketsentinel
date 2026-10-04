"""Data cleaning, validation, and sanitization for time-series and ticker data."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from marketsentinel.core.exceptions import DataProcessingError
from marketsentinel.processing.models import CandlePoint, TickerData


class DataCleaner:
    """Robust cleaner and validator for financial market time-series and snapshots."""

    @staticmethod
    def clean_ticker(raw_item: dict, symbol: str, currency: str = "usd") -> TickerData:
        """Sanitizes raw API payload into a valid TickerData instance with fallback defaults."""
        try:
            price = float(raw_item.get(currency, 0.0) or 0.0)
            change = float(raw_item.get(f"{currency}_24h_change", 0.0) or 0.0)
            volume = float(raw_item.get(f"{currency}_24h_vol", 0.0) or 0.0)
            market_cap = float(raw_item.get(f"{currency}_market_cap", 0.0) or 0.0)

            # Safeguard against negative or zero corrupted prices
            if price <= 0:
                price = 1.0  # safe floor

            # Estimate high/low if missing in basic API responses
            high = price * (1.0 + abs(change) / 100.0 * 0.7)
            low = price * (1.0 - abs(change) / 100.0 * 0.7)

            name = symbol.replace("-", " ").capitalize()
            symbol_map = {
                "bitcoin": "BTC",
                "ethereum": "ETH",
                "solana": "SOL",
                "cardano": "ADA",
                "ripple": "XRP",
                "dogecoin": "DOGE",
                "polkadot": "DOT",
                "avalanche-2": "AVAX",
                "chainlink": "LINK",
            }
            display_symbol = symbol_map.get(symbol.lower(), symbol.upper()[:5])

            return TickerData(
                symbol=display_symbol,
                name=name,
                price=price,
                currency=currency.upper(),
                change_24h_pct=change,
                volume_24h=volume,
                high_24h=high,
                low_24h=low,
                market_cap=market_cap,
                last_updated=datetime.now(timezone.utc),
            )
        except Exception as e:
            raise DataProcessingError(f"Failed to clean ticker for symbol '{symbol}': {e}") from e

    @staticmethod
    def clean_timeseries(raw_points: list[list[float | int]]) -> list[CandlePoint]:
        """Cleans and orders chronological candle price points [timestamp_ms, price].

        - Filters NaN and non-positive prices
        - Deduplicates identical timestamps
        - Sorts in ascending chronological order
        """
        if not raw_points:
            return []

        cleaned: list[CandlePoint] = []
        seen_timestamps = set()

        for pt in raw_points:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue

            ts_ms, val = pt[0], pt[1]
            if val is None or math.isnan(val) or val <= 0:
                continue

            try:
                dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            except (ValueError, OverflowError):
                continue

            if dt in seen_timestamps:
                continue

            seen_timestamps.add(dt)
            cleaned.append(CandlePoint(timestamp=dt, price=float(val)))

        # Chronological sort
        cleaned.sort(key=lambda x: x.timestamp)
        return cleaned
