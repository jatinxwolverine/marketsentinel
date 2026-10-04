"""Domain data models and dataclasses for market metrics, indicators, and alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TickerData:
    symbol: str
    name: str
    price: float
    currency: str
    change_24h_pct: float
    volume_24h: float
    high_24h: float
    low_24h: float
    market_cap: float
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": self.price,
            "currency": self.currency,
            "change_24h_pct": self.change_24h_pct,
            "volume_24h": self.volume_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "market_cap": self.market_cap,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class CandlePoint:
    timestamp: datetime
    price: float


@dataclass
class HistoricalSeries:
    symbol: str
    currency: str
    prices: list[CandlePoint]
    days: int


@dataclass
class TechnicalSignals:
    symbol: str
    current_price: float
    rsi_14: float
    sma_20: float | None
    sma_50: float | None
    ema_12: float | None
    ema_26: float | None
    macd_line: float | None
    macd_signal: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    volatility_pct: float
    trend: str  # "BULLISH", "BEARISH", "NEUTRAL"
    signals: list[str] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "current_price": self.current_price,
            "rsi_14": round(self.rsi_14, 2),
            "sma_20": round(self.sma_20, 2) if self.sma_20 else None,
            "sma_50": round(self.sma_50, 2) if self.sma_50 else None,
            "macd_line": round(self.macd_line, 2) if self.macd_line else None,
            "bollinger_upper": round(self.bollinger_upper, 2) if self.bollinger_upper else None,
            "bollinger_lower": round(self.bollinger_lower, 2) if self.bollinger_lower else None,
            "volatility_pct": round(self.volatility_pct, 2),
            "trend": self.trend,
            "signals": self.signals,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class AlertTrigger:
    symbol: str
    rule_name: str
    severity: str  # "INFO", "WARNING", "CRITICAL"
    trigger_value: float
    threshold_value: float
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "rule_name": self.rule_name,
            "severity": self.severity,
            "trigger_value": self.trigger_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarketSnapshotSummary:
    total_market_cap: float
    avg_24h_change: float
    top_gainer: TickerData | None
    top_loser: TickerData | None
    overall_sentiment: str  # "BULLISH", "BEARISH", "NEUTRAL"
    tickers: list[TickerData] = field(default_factory=list)
    signals: list[TechnicalSignals] = field(default_factory=list)
    alerts: list[AlertTrigger] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
