"""Scheduled task implementations for data ingestion, indicator evaluation, reporting, and backups."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from marketsentinel.alerts.dispatcher import AlertDispatcher
from marketsentinel.alerts.rules import AlertRuleEvaluator
from marketsentinel.api.coingecko import CoinGeckoService
from marketsentinel.core.config import AppConfig
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.indicators import TechnicalAnalysisEngine
from marketsentinel.reporting.pdf_generator import ExecutiveReportGenerator
from marketsentinel.storage.backup import BackupManager
from marketsentinel.storage.database import DatabaseManager

logger = get_logger("marketsentinel.scheduler.jobs")


class AutomationJobs:
    """Encapsulates periodic autonomous jobs executed by the scheduler engine."""

    def __init__(self, config: AppConfig, db: DatabaseManager) -> None:
        self.config = config
        self.db = db
        self.api_service = CoinGeckoService(
            base_url=config.api.base_url,
            timeout=config.api.timeout,
            api_key=config.api.api_key,
        )
        self.alert_evaluator = AlertRuleEvaluator(config.alerts)
        self.alert_dispatcher = AlertDispatcher(config.alerts, db=db)
        self.report_generator = ExecutiveReportGenerator(config.reporting)
        self.backup_manager = BackupManager(
            db_path=config.storage.db_path,
            backup_dir=config.backup.backup_dir,
            retention_count=config.backup.retention_count,
            compression=config.backup.compression,
        )
        self._cached_candles: dict[str, list[CandlePoint]] = {}

    def run_ingestion_and_indicators(self) -> dict:
        """Fetches live market data, computes indicators, and persists snapshots to database."""
        start_time = time.perf_counter()
        logger.info("[cyan]Starting scheduled Market Ingestion & Indicator Job...[/cyan]")

        try:
            tickers = self.api_service.fetch_tickers(self.config.symbols, currency=self.config.currency)
            self.db.save_tickers(tickers)

            signals = []
            for t in tickers:
                candles = self.api_service.fetch_historical_candles(t.symbol, days=14, currency=self.config.currency)
                self._cached_candles[t.symbol] = candles
                sig = TechnicalAnalysisEngine.evaluate(t.symbol, current_price=t.price, candles=candles)
                signals.append(sig)

            self.db.save_signals(signals)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="INGESTION_AND_INDICATORS",
                status="SUCCESS",
                duration_ms=elapsed_ms,
                details=f"Processed {len(tickers)} assets, calculated {len(signals)} indicator sets.",
            )
            logger.info(
                f"[bold green]Ingestion Completed:[/bold green] {len(tickers)} assets processed in {elapsed_ms:.1f}ms"
            )
            return {"status": "SUCCESS", "tickers_count": len(tickers), "signals_count": len(signals)}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="INGESTION_AND_INDICATORS",
                status="FAILED",
                duration_ms=elapsed_ms,
                details=str(e),
            )
            logger.error(f"Ingestion job failed: {e}")
            return {"status": "FAILED", "error": str(e)}

    def run_alert_evaluation(self) -> dict:
        """Evaluates latest market data against alert rules and dispatches notifications."""
        start_time = time.perf_counter()
        logger.info("[yellow]Evaluating Real-Time Alert Triggers...[/yellow]")

        try:
            latest_tickers = self.db.get_latest_tickers()
            triggered_alerts = []

            for t in latest_tickers:
                # 1. Evaluate ticker rules
                ticker_alerts = self.alert_evaluator.evaluate_ticker(t)
                for a in ticker_alerts:
                    self.alert_dispatcher.dispatch(a)
                    triggered_alerts.append(a)

                # 2. Evaluate signals
                candles = self.db.get_price_history(t.symbol, limit=30)
                sig = TechnicalAnalysisEngine.evaluate(t.symbol, t.price, candles)
                sig_alerts = self.alert_evaluator.evaluate_signals(sig)
                for a in sig_alerts:
                    self.alert_dispatcher.dispatch(a)
                    triggered_alerts.append(a)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="ALERT_EVALUATION",
                status="SUCCESS",
                duration_ms=elapsed_ms,
                details=f"Evaluated {len(latest_tickers)} assets, fired {len(triggered_alerts)} alerts.",
            )
            logger.info(
                f"[bold yellow]Alert Evaluation Completed:[/bold yellow] {len(triggered_alerts)} triggers fired."
            )
            return {"status": "SUCCESS", "alerts_count": len(triggered_alerts)}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="ALERT_EVALUATION",
                status="FAILED",
                duration_ms=elapsed_ms,
                details=str(e),
            )
            logger.error(f"Alert evaluation job failed: {e}")
            return {"status": "FAILED", "error": str(e)}

    def run_daily_digest_report(self) -> dict:
        """Assembles executive PDF report with embedded charts and summaries."""
        start_time = time.perf_counter()
        logger.info("[bold blue]Generating Executive Daily PDF Digest...[/bold blue]")

        try:
            tickers = self.db.get_latest_tickers()
            if not tickers:
                tickers = self.api_service.fetch_tickers(self.config.symbols, currency=self.config.currency)
                self.db.save_tickers(tickers)

            signals = []
            candle_map = {}
            for t in tickers:
                candles = (
                    self._cached_candles.get(t.symbol)
                    or self.db.get_price_history(t.symbol, limit=60)
                )
                if not candles:
                    candles = self.api_service.fetch_historical_candles(t.symbol, days=14, currency=self.config.currency)
                candle_map[t.symbol] = candles
                sig = TechnicalAnalysisEngine.evaluate(t.symbol, t.price, candles)
                signals.append(sig)

            alerts: list[AlertTrigger] = []
            for t in tickers:
                alerts.extend(self.alert_evaluator.evaluate_ticker(t))

            pdf_path = self.report_generator.generate_report(
                tickers=tickers,
                signals=signals,
                alerts=alerts,
                candle_history=candle_map,
            )

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="DAILY_DIGEST_REPORT",
                status="SUCCESS",
                duration_ms=elapsed_ms,
                details=f"Generated PDF: {pdf_path.name}",
            )
            return {"status": "SUCCESS", "pdf_path": str(pdf_path)}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="DAILY_DIGEST_REPORT",
                status="FAILED",
                duration_ms=elapsed_ms,
                details=str(e),
            )
            logger.error(f"Daily digest report job failed: {e}")
            return {"status": "FAILED", "error": str(e)}

    def run_automated_backup(self) -> dict:
        """Executes snapshot backup, SHA256 verification, and cloud retention rotation."""
        start_time = time.perf_counter()
        logger.info("[bold magenta]Executing Automated Database & Asset Backup...[/bold magenta]")

        try:
            archive_path = self.backup_manager.create_backup(tag="scheduled")
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            self.db.record_job_run(
                job_name="AUTOMATED_BACKUP",
                status="SUCCESS",
                duration_ms=elapsed_ms,
                details=f"Created backup archive: {archive_path.name}",
            )
            return {"status": "SUCCESS", "archive": str(archive_path)}

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.db.record_job_run(
                job_name="AUTOMATED_BACKUP",
                status="FAILED",
                duration_ms=elapsed_ms,
                details=str(e),
            )
            logger.error(f"Backup job failed: {e}")
            return {"status": "FAILED", "error": str(e)}
