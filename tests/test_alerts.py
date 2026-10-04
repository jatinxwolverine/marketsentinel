"""Tests for rule-based alerting and multi-channel dispatcher."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from marketsentinel.alerts.dispatcher import AlertDispatcher
from marketsentinel.alerts.rules import AlertRuleEvaluator
from marketsentinel.core.config import AlertConfig
from marketsentinel.processing.models import AlertTrigger, TechnicalSignals, TickerData
from marketsentinel.storage.database import DatabaseManager


@pytest.fixture
def alert_config():
    return AlertConfig(
        enabled=True,
        console_enabled=True,
        webhook_enabled=False,
        email_enabled=False,
        price_change_threshold_pct=3.0,
        rsi_oversold=30.0,
        rsi_overbought=70.0,
        volatility_spike_pct=5.0,
    )


def test_price_surge_alert(alert_config):
    evaluator = AlertRuleEvaluator(alert_config)

    # Ticker with +5.2% surge (exceeds 3.0% threshold)
    t = TickerData(
        symbol="BTC",
        name="Bitcoin",
        price=65000.0,
        currency="USD",
        change_24h_pct=5.2,
        volume_24h=1000000.0,
        high_24h=66000.0,
        low_24h=64000.0,
        market_cap=1200000000.0,
    )
    alerts = evaluator.evaluate_ticker(t)
    assert len(alerts) >= 1
    assert alerts[0].rule_name == "PRICE_CHANGE_SURGE"
    assert alerts[0].symbol == "BTC"


def test_rsi_extremes_alert(alert_config):
    evaluator = AlertRuleEvaluator(alert_config)

    # Oversold signal
    sig_oversold = TechnicalSignals(
        symbol="ETH",
        current_price=3000.0,
        rsi_14=24.5,
        sma_20=3100.0,
        sma_50=3200.0,
        ema_12=3050.0,
        ema_26=3150.0,
        macd_line=-20.0,
        macd_signal=-15.0,
        bollinger_upper=3300.0,
        bollinger_lower=2900.0,
        volatility_pct=4.1,
        trend="BEARISH",
        signals=["RSI_OVERSOLD"],
    )
    alerts = evaluator.evaluate_signals(sig_oversold)
    assert any(a.rule_name == "RSI_OVERSOLD_OPPORTUNITY" for a in alerts)


def test_alert_dispatcher(tmp_path, alert_config):
    db_file = tmp_path / "test_alerts.db"
    db = DatabaseManager(db_path=str(db_file), enable_wal=False)
    dispatcher = AlertDispatcher(alert_config, db=db)

    alert = AlertTrigger(
        symbol="SOL",
        rule_name="TEST_TRIGGER",
        severity="WARNING",
        trigger_value=4.5,
        threshold_value=3.0,
        message="Solana test surge notification",
        timestamp=datetime.now(timezone.utc),
    )

    results = dispatcher.dispatch(alert)
    assert results.get("console") is True
    assert results.get("audit_log") is True

    # Check database persistence
    recent = db.get_recent_alerts(limit=5)
    assert len(recent) >= 1
    assert recent[0]["symbol"] == "SOL"
