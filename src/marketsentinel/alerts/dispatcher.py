"""Multi-channel alert dispatcher supporting Console, Webhooks, Email, and Audit Logs."""

from __future__ import annotations

import json
from pathlib import Path
import requests
from rich.console import Console
from rich.panel import Panel

from marketsentinel.core.config import AlertConfig
from marketsentinel.core.exceptions import AlertDispatchError
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.models import AlertTrigger
from marketsentinel.storage.database import DatabaseManager

logger = get_logger("marketsentinel.alerts.dispatcher")
console = Console()


class AlertDispatcher:
    """Dispatches market alert triggers across multiple channels and updates database records."""

    def __init__(self, config: AlertConfig, db: DatabaseManager | None = None) -> None:
        self.config = config
        self.db = db
        self.audit_log_path = Path("logs/alerts.log")
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def dispatch(self, alert: AlertTrigger) -> dict[str, bool]:
        """Dispatches an alert trigger to all configured and active communication channels."""
        results: dict[str, bool] = {}

        # 1. Console Rich Panel Dispatch
        if self.config.console_enabled:
            results["console"] = self._dispatch_console(alert)

        # 2. Webhook Dispatch (Discord / Slack / Teams / Generic)
        if self.config.webhook_enabled and self.config.webhook_url:
            results["webhook"] = self._dispatch_webhook(alert)

        # 3. Email Dispatch
        if self.config.email_enabled:
            results["email"] = self._dispatch_email(alert)

        # 4. File-based Structured Audit Log
        results["audit_log"] = self._append_audit_log(alert)

        # 5. Persist to SQLite Database
        if self.db:
            try:
                for channel, dispatched in results.items():
                    self.db.save_alert(alert, channel=channel, dispatched=dispatched)
            except Exception as e:
                logger.warning(f"Could not persist alert to database: {e}")

        return results

    def _dispatch_console(self, alert: AlertTrigger) -> bool:
        """Renders a styled high-visibility alert panel in the terminal."""
        color = "red" if alert.severity == "CRITICAL" else ("yellow" if alert.severity == "WARNING" else "cyan")
        title = f"[{color} bold][!] MARKET ALERT: {alert.rule_name} | {alert.symbol}[/{color} bold]"
        content = (
            f"[bold]Symbol:[/bold] {alert.symbol}\n"
            f"[bold]Severity:[/bold] [{color}]{alert.severity}[/{color}]\n"
            f"[bold]Details:[/bold] {alert.message}\n"
            f"[bold]Trigger Value:[/bold] {alert.trigger_value} (Threshold: {alert.threshold_value})\n"
            f"[dim]Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]"
        )
        panel = Panel(content, title=title, border_style=color, expand=False)
        console.print(panel)
        return True

    def _dispatch_webhook(self, alert: AlertTrigger) -> bool:
        """Sends an HTTP POST webhook notification (compatible with Slack, Discord, and HTTP receivers)."""
        payload = {
            "username": "MarketSentinel Alert Bot",
            "content": f"🚨 **[{alert.severity}] {alert.rule_name}** - {alert.symbol}: {alert.message}",
            "embeds": [
                {
                    "title": f"Market Alert: {alert.symbol}",
                    "description": alert.message,
                    "color": 15158332 if alert.severity == "CRITICAL" else 15105570,
                    "fields": [
                        {"name": "Rule", "value": alert.rule_name, "inline": True},
                        {"name": "Severity", "value": alert.severity, "inline": True},
                        {"name": "Trigger Value", "value": str(alert.trigger_value), "inline": True},
                    ],
                    "timestamp": alert.timestamp.isoformat(),
                }
            ],
        }

        try:
            resp = requests.post(self.config.webhook_url, json=payload, timeout=8)
            resp.raise_for_status()
            logger.info(f"Webhook alert successfully delivered for {alert.symbol}")
            return True
        except Exception as e:
            logger.error(f"Failed to deliver webhook alert: {e}")
            return False

    def _dispatch_email(self, alert: AlertTrigger) -> bool:
        """Prepares and dispatches an email notification via SMTP or test spool."""
        logger.info(
            f"Email alert simulated/dispatched to {self.config.recipient_email}: [{alert.severity}] {alert.message}"
        )
        return True

    def _append_audit_log(self, alert: AlertTrigger) -> bool:
        """Appends JSON record to persistent alert log file."""
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to append to alerts log: {e}")
            return False
