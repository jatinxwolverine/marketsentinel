"""Enterprise SQLite persistence layer with WAL mode and audit tracking."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from marketsentinel.core.exceptions import StorageError
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.models import (
    AlertTrigger,
    CandlePoint,
    TechnicalSignals,
    TickerData,
)

logger = get_logger("marketsentinel.storage.db")


class DatabaseManager:
    """Manages SQLite database connections, schema migrations, and queries."""

    def __init__(self, db_path: str = "data/marketsentinel.db", enable_wal: bool = True) -> None:
        self.db_path = Path(db_path)
        self.enable_wal = enable_wal
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        if self.enable_wal:
            conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes database tables and performance indexes."""
        try:
            with self._get_connection() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS market_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        name TEXT NOT NULL,
                        price REAL NOT NULL,
                        currency TEXT NOT NULL,
                        change_24h_pct REAL NOT NULL,
                        volume_24h REAL NOT NULL,
                        high_24h REAL NOT NULL,
                        low_24h REAL NOT NULL,
                        market_cap REAL NOT NULL,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time 
                    ON market_snapshots(symbol, recorded_at);

                    CREATE TABLE IF NOT EXISTS technical_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        current_price REAL NOT NULL,
                        rsi_14 REAL NOT NULL,
                        sma_20 REAL,
                        sma_50 REAL,
                        volatility_pct REAL NOT NULL,
                        trend TEXT NOT NULL,
                        signals_json TEXT NOT NULL,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS idx_signals_symbol_time 
                    ON technical_signals(symbol, calculated_at);

                    CREATE TABLE IF NOT EXISTS alert_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        rule_name TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        trigger_value REAL NOT NULL,
                        threshold_value REAL NOT NULL,
                        message TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        dispatched INTEGER NOT NULL DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE INDEX IF NOT EXISTS idx_alerts_symbol_time 
                    ON alert_records(symbol, created_at);

                    CREATE TABLE IF NOT EXISTS scheduler_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration_ms REAL NOT NULL,
                        details TEXT,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            logger.debug(f"Database initialized successfully at {self.db_path}")
        except Exception as e:
            raise StorageError(f"Failed to initialize database: {e}") from e

    def save_tickers(self, tickers: list[TickerData]) -> int:
        """Persists a batch of market snapshots."""
        if not tickers:
            return 0

        query = """
            INSERT INTO market_snapshots (
                symbol, name, price, currency, change_24h_pct, volume_24h, high_24h, low_24h, market_cap, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        records = [
            (
                t.symbol,
                t.name,
                t.price,
                t.currency,
                t.change_24h_pct,
                t.volume_24h,
                t.high_24h,
                t.low_24h,
                t.market_cap,
                t.last_updated.isoformat(),
            )
            for t in tickers
        ]

        try:
            with self._get_connection() as conn:
                conn.executemany(query, records)
            return len(records)
        except Exception as e:
            logger.error(f"Failed to save tickers: {e}")
            raise StorageError(f"Database error saving tickers: {e}") from e

    def save_signals(self, signals: list[TechnicalSignals]) -> int:
        """Persists technical analysis indicator results."""
        if not signals:
            return 0

        query = """
            INSERT INTO technical_signals (
                symbol, current_price, rsi_14, sma_20, sma_50, volatility_pct, trend, signals_json, calculated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        records = [
            (
                s.symbol,
                s.current_price,
                s.rsi_14,
                s.sma_20,
                s.sma_50,
                s.volatility_pct,
                s.trend,
                json.dumps(s.signals),
                s.calculated_at.isoformat(),
            )
            for s in signals
        ]

        try:
            with self._get_connection() as conn:
                conn.executemany(query, records)
            return len(records)
        except Exception as e:
            logger.error(f"Failed to save technical signals: {e}")
            raise StorageError(f"Database error saving signals: {e}") from e

    def save_alert(self, alert: AlertTrigger, channel: str = "console", dispatched: bool = True) -> int:
        """Records an alert event to the audit trail."""
        query = """
            INSERT INTO alert_records (
                symbol, rule_name, severity, trigger_value, threshold_value, message, channel, dispatched, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    query,
                    (
                        alert.symbol,
                        alert.rule_name,
                        alert.severity,
                        alert.trigger_value,
                        alert.threshold_value,
                        alert.message,
                        channel,
                        1 if dispatched else 0,
                        alert.timestamp.isoformat(),
                    ),
                )
                return cur.lastrowid or 1
        except Exception as e:
            logger.error(f"Failed to record alert: {e}")
            raise StorageError(f"Database error recording alert: {e}") from e

    def record_job_run(self, job_name: str, status: str, duration_ms: float, details: str = "") -> None:
        """Records a scheduled task execution log entry."""
        query = """
            INSERT INTO scheduler_runs (job_name, status, duration_ms, details)
            VALUES (?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query, (job_name, status, duration_ms, details))
        except Exception as e:
            logger.warning(f"Could not record scheduler run: {e}")

    def get_latest_tickers(self) -> list[TickerData]:
        """Retrieves the most recent market snapshot for each monitored symbol."""
        query = """
            SELECT s.* FROM market_snapshots s
            INNER JOIN (
                SELECT symbol, MAX(recorded_at) as max_time
                FROM market_snapshots
                GROUP BY symbol
            ) latest ON s.symbol = latest.symbol AND s.recorded_at = latest.max_time
            ORDER BY s.market_cap DESC
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(query).fetchall()

            tickers = []
            for r in rows:
                tickers.append(
                    TickerData(
                        symbol=r["symbol"],
                        name=r["name"],
                        price=r["price"],
                        currency=r["currency"],
                        change_24h_pct=r["change_24h_pct"],
                        volume_24h=r["volume_24h"],
                        high_24h=r["high_24h"],
                        low_24h=r["low_24h"],
                        market_cap=r["market_cap"],
                        last_updated=datetime.fromisoformat(r["recorded_at"])
                        if "T" in str(r["recorded_at"])
                        else datetime.now(timezone.utc),
                    )
                )
            return tickers
        except Exception as e:
            logger.error(f"Failed to query latest tickers: {e}")
            return []

    def get_price_history(self, symbol: str, limit: int = 100) -> list[CandlePoint]:
        """Retrieves chronological price history for an asset from stored snapshots."""
        query = """
            SELECT price, recorded_at FROM market_snapshots
            WHERE symbol = ?
            ORDER BY recorded_at DESC
            LIMIT ?
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(query, (symbol.upper(), limit)).fetchall()

            candles: list[CandlePoint] = []
            for r in reversed(rows):
                dt = (
                    datetime.fromisoformat(r["recorded_at"])
                    if "T" in str(r["recorded_at"])
                    else datetime.now(timezone.utc)
                )
                candles.append(CandlePoint(timestamp=dt, price=float(r["price"])))
            return candles
        except Exception as e:
            logger.error(f"Failed to query price history: {e}")
            return []

    def get_recent_alerts(self, limit: int = 20) -> list[dict]:
        """Retrieves recent triggered alerts for reporting and display."""
        query = """
            SELECT * FROM alert_records
            ORDER BY created_at DESC
            LIMIT ?
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(query, (limit,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to query recent alerts: {e}")
            return []

    def get_system_stats(self) -> dict:
        """Retrieves high-level storage and pipeline telemetry."""
        stats = {
            "snapshot_count": 0,
            "signal_count": 0,
            "alert_count": 0,
            "job_run_count": 0,
            "db_size_bytes": 0,
        }
        try:
            if self.db_path.exists():
                stats["db_size_bytes"] = self.db_path.stat().st_size

            with self._get_connection() as conn:
                stats["snapshot_count"] = conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0]
                stats["signal_count"] = conn.execute("SELECT COUNT(*) FROM technical_signals").fetchone()[0]
                stats["alert_count"] = conn.execute("SELECT COUNT(*) FROM alert_records").fetchone()[0]
                stats["job_run_count"] = conn.execute("SELECT COUNT(*) FROM scheduler_runs").fetchone()[0]
        except Exception as e:
            logger.warning(f"Error reading system stats: {e}")
        return stats
