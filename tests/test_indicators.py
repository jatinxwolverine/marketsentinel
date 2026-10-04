"""Tests for mathematical technical indicator calculations and trend analysis."""

from datetime import datetime, timezone
import pytest
from marketsentinel.processing.cleaner import DataCleaner
from marketsentinel.processing.indicators import TechnicalAnalysisEngine
from marketsentinel.processing.models import CandlePoint


def test_calculate_sma():
    prices = [10.0, 20.0, 30.0, 40.0, 50.0]
    sma_3 = TechnicalAnalysisEngine.calculate_sma(prices, window=3)
    assert sma_3 == 40.0  # (30 + 40 + 50) / 3

    assert TechnicalAnalysisEngine.calculate_sma(prices, window=10) is None


def test_calculate_ema():
    prices = [10.0, 10.0, 10.0, 10.0, 20.0]
    ema_4 = TechnicalAnalysisEngine.calculate_ema(prices, window=4)
    assert ema_4 is not None
    assert ema_4 > 10.0


def test_calculate_rsi_neutral_and_extremes():
    # Constant prices -> RSI should be neutral or 50
    neutral_prices = [100.0] * 20
    rsi_neutral = TechnicalAnalysisEngine.calculate_rsi(neutral_prices, period=14)
    assert 40.0 <= rsi_neutral <= 60.0

    # Strictly rising prices -> RSI should be 100
    rising_prices = [float(i) for i in range(1, 30)]
    rsi_high = TechnicalAnalysisEngine.calculate_rsi(rising_prices, period=14)
    assert rsi_high > 80.0

    # Strictly falling prices -> RSI should be very low
    falling_prices = [float(100 - i) for i in range(30)]
    rsi_low = TechnicalAnalysisEngine.calculate_rsi(falling_prices, period=14)
    assert rsi_low < 20.0


def test_calculate_bollinger_bands():
    prices = [float(100 + (i % 5)) for i in range(25)]
    lower, mid, upper = TechnicalAnalysisEngine.calculate_bollinger_bands(prices, window=20)
    assert lower is not None and mid is not None and upper is not None
    assert lower < mid < upper


def test_full_indicator_evaluation():
    now = datetime.now(timezone.utc)
    # Generate 30 candles
    candles = [CandlePoint(timestamp=now, price=50.0 + (i * 0.5)) for i in range(30)]
    signals = TechnicalAnalysisEngine.evaluate("BTC", current_price=65.0, candles=candles)

    assert signals.symbol == "BTC"
    assert signals.current_price == 65.0
    assert 0 <= signals.rsi_14 <= 100
    assert signals.trend in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert isinstance(signals.signals, list)


def test_data_cleaner_timeseries():
    raw = [
        [1700000000000, 100.5],
        [1700000000000, 100.5],  # duplicate
        [1700001000000, -5.0],   # invalid negative
        [1700002000000, float("nan")],  # NaN
        [1700003000000, 105.2],
    ]
    cleaned = DataCleaner.clean_timeseries(raw)
    assert len(cleaned) == 2
    assert cleaned[0].price == 100.5
    assert cleaned[1].price == 105.2
