"""Enterprise configuration management with YAML support and environment variable overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml

from marketsentinel.core.exceptions import ConfigurationError


@dataclass
class APIConfig:
    provider: str = "coingecko"
    timeout: int = 15
    retry_attempts: int = 3
    retry_backoff: float = 1.5
    rate_limit_sleep: float = 1.0
    api_key: str | None = None
    base_url: str = "https://api.coingecko.com/api/v3"


@dataclass
class AlertConfig:
    enabled: bool = True
    console_enabled: bool = True
    webhook_enabled: bool = False
    webhook_url: str = ""
    email_enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    recipient_email: str = ""
    price_change_threshold_pct: float = 4.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    volatility_spike_pct: float = 7.5


@dataclass
class StorageConfig:
    db_path: str = "data/marketsentinel.db"
    enable_wal: bool = True


@dataclass
class BackupConfig:
    enabled: bool = True
    backup_dir: str = "backups"
    retention_count: int = 5
    compression: str = "gz"  # 'gz' or 'zip'
    cloud_sync_simulated: bool = True


@dataclass
class ReportingConfig:
    output_dir: str = "reports"
    company_name: str = "MarketSentinel Analytics Corp."
    title: str = "Market Intelligence & Risk Report"
    include_charts: bool = True
    theme: str = "executive_dark"


@dataclass
class SchedulerConfig:
    ingestion_interval_seconds: int = 60
    alert_interval_seconds: int = 60
    daily_report_time: str = "18:00"
    backup_interval_hours: int = 6


@dataclass
class AppConfig:
    app_name: str = "MarketSentinel"
    environment: str = "production"
    currency: str = "usd"
    debug: bool = False
    symbols: list[str] = field(
        default_factory=lambda: ["bitcoin", "ethereum", "solana", "cardano", "ripple"]
    )
    api: APIConfig = field(default_factory=APIConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Parses a dictionary into typed configuration dataclasses."""
        api_data = data.get("api", {})
        alerts_data = data.get("alerts", {})
        storage_data = data.get("storage", {})
        backup_data = data.get("backup", {})
        reporting_data = data.get("reporting", {})
        scheduler_data = data.get("scheduler", {})

        return cls(
            app_name=data.get("app_name", "MarketSentinel"),
            environment=data.get("environment", "production"),
            currency=data.get("currency", "usd"),
            debug=data.get("debug", False),
            symbols=data.get(
                "symbols", ["bitcoin", "ethereum", "solana", "cardano", "ripple"]
            ),
            api=APIConfig(**api_data),
            alerts=AlertConfig(**alerts_data),
            storage=StorageConfig(**storage_data),
            backup=BackupConfig(**backup_data),
            reporting=ReportingConfig(**reporting_data),
            scheduler=SchedulerConfig(**scheduler_data),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes configuration into a dictionary."""
        return {
            "app_name": self.app_name,
            "environment": self.environment,
            "currency": self.currency,
            "debug": self.debug,
            "symbols": self.symbols,
            "api": self.api.__dict__,
            "alerts": self.alerts.__dict__,
            "storage": self.storage.__dict__,
            "backup": self.backup.__dict__,
            "reporting": self.reporting.__dict__,
            "scheduler": self.scheduler.__dict__,
        }


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Loads application configuration from YAML file or falls back to production defaults.

    Args:
        config_path: Path to YAML config file. If None, checks default paths.

    Returns:
        Populated AppConfig instance with environment variable overrides applied.
    """
    candidates = [
        Path(config_path) if config_path else None,
        Path("config/config.yaml"),
        Path("config/config.example.yaml"),
    ]

    target_path = None
    for cand in candidates:
        if cand and cand.exists():
            target_path = cand
            break

    if target_path and target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
            config = AppConfig.from_dict(raw_data)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to parse configuration file '{target_path}': {e}"
            ) from e
    else:
        config = AppConfig()

    # Environment variable overrides (e.g. MARKETSENTINEL_CURRENCY, MARKETSENTINEL_WEBHOOK_URL)
    if "MARKETSENTINEL_CURRENCY" in os.environ:
        config.currency = os.environ["MARKETSENTINEL_CURRENCY"]
    if "MARKETSENTINEL_WEBHOOK_URL" in os.environ:
        config.alerts.webhook_url = os.environ["MARKETSENTINEL_WEBHOOK_URL"]
        config.alerts.webhook_enabled = True
    if "MARKETSENTINEL_DB_PATH" in os.environ:
        config.storage.db_path = os.environ["MARKETSENTINEL_DB_PATH"]
    if "MARKETSENTINEL_DEBUG" in os.environ:
        config.debug = os.environ["MARKETSENTINEL_DEBUG"].lower() in ("true", "1", "yes")

    return config
