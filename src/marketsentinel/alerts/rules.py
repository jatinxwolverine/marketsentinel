"""Rule evaluation engine for real-time market anomaly and technical trigger detection."""

from __future__ import annotations

from marketsentinel.core.config import AlertConfig
from marketsentinel.processing.models import AlertTrigger, TechnicalSignals, TickerData


class AlertRuleEvaluator:
    """Evaluates incoming market data and technical signals against alert rule definitions."""

    def __init__(self, config: AlertConfig) -> None:
        self.config = config

    def evaluate_ticker(self, ticker: TickerData) -> list[AlertTrigger]:
        """Evaluates price movement and volatility triggers on raw ticker snapshot."""
        alerts: list[AlertTrigger] = []

        # 1. 24h Price Percentage Change Surge Rule
        threshold = self.config.price_change_threshold_pct
        if abs(ticker.change_24h_pct) >= threshold:
            direction = "SURGED" if ticker.change_24h_pct > 0 else "PLUMMETED"
            severity = "CRITICAL" if abs(ticker.change_24h_pct) >= (threshold * 2) else "WARNING"
            alerts.append(
                AlertTrigger(
                    symbol=ticker.symbol,
                    rule_name="PRICE_CHANGE_SURGE",
                    severity=severity,
                    trigger_value=ticker.change_24h_pct,
                    threshold_value=threshold,
                    message=(
                        f"{ticker.symbol} has {direction} by {ticker.change_24h_pct:+.2f}% in 24h "
                        f"(Threshold: ±{threshold}%, Current Price: ${ticker.price:,.2f})"
                    ),
                )
            )

        # 2. Daily Volatility Spread Rule
        if ticker.low_24h > 0:
            spread_pct = ((ticker.high_24h - ticker.low_24h) / ticker.low_24h) * 100.0
            if spread_pct >= self.config.volatility_spike_pct:
                alerts.append(
                    AlertTrigger(
                        symbol=ticker.symbol,
                        rule_name="VOLATILITY_SPREAD_SPIKE",
                        severity="WARNING",
                        trigger_value=round(spread_pct, 2),
                        threshold_value=self.config.volatility_spike_pct,
                        message=(
                            f"{ticker.symbol} daily range spread reached {spread_pct:.2f}% "
                            f"(High: ${ticker.high_24h:,.2f} | Low: ${ticker.low_24h:,.2f})"
                        ),
                    )
                )

        return alerts

    def evaluate_signals(self, signal: TechnicalSignals) -> list[AlertTrigger]:
        """Evaluates technical indicator thresholds (RSI, Bollinger Bands, Moving Averages)."""
        alerts: list[AlertTrigger] = []

        # 3. RSI Oversold Condition
        if signal.rsi_14 <= self.config.rsi_oversold:
            alerts.append(
                AlertTrigger(
                    symbol=signal.symbol,
                    rule_name="RSI_OVERSOLD_OPPORTUNITY",
                    severity="INFO",
                    trigger_value=signal.rsi_14,
                    threshold_value=self.config.rsi_oversold,
                    message=(
                        f"{signal.symbol} RSI-14 is OVERSOLD at {signal.rsi_14:.1f} "
                        f"(<= {self.config.rsi_oversold}). Bullish reversal bounce possible."
                    ),
                )
            )

        # 4. RSI Overbought Condition
        elif signal.rsi_14 >= self.config.rsi_overbought:
            alerts.append(
                AlertTrigger(
                    symbol=signal.symbol,
                    rule_name="RSI_OVERBOUGHT_CORRECTION_RISK",
                    severity="WARNING",
                    trigger_value=signal.rsi_14,
                    threshold_value=self.config.rsi_overbought,
                    message=(
                        f"{signal.symbol} RSI-14 is OVERBOUGHT at {signal.rsi_14:.1f} "
                        f"(>= {self.config.rsi_overbought}). Price correction risk elevated."
                    ),
                )
            )

        # 5. Bollinger Bands Breakouts
        if "BOLLINGER_UPPER_BREAKOUT" in signal.signals:
            alerts.append(
                AlertTrigger(
                    symbol=signal.symbol,
                    rule_name="BOLLINGER_UPPER_BREAKOUT",
                    severity="INFO",
                    trigger_value=signal.current_price,
                    threshold_value=signal.bollinger_upper or signal.current_price,
                    message=f"{signal.symbol} penetrated upper Bollinger Band (${signal.bollinger_upper:,.2f}).",
                )
            )
        elif "BOLLINGER_LOWER_BREAKOUT" in signal.signals:
            alerts.append(
                AlertTrigger(
                    symbol=signal.symbol,
                    rule_name="BOLLINGER_LOWER_BREAKOUT",
                    severity="WARNING",
                    trigger_value=signal.current_price,
                    threshold_value=signal.bollinger_lower or signal.current_price,
                    message=f"{signal.symbol} dropped below lower Bollinger Band (${signal.bollinger_lower:,.2f}).",
                )
            )

        return alerts
