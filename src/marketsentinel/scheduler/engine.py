"""Enterprise autonomous scheduler engine with cron, interval, and signal handling."""

from __future__ import annotations

import signal
import sys
import time
from datetime import datetime, timezone
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from rich.console import Console
from rich.table import Table

from marketsentinel.core.config import AppConfig
from marketsentinel.core.logging import get_logger
from marketsentinel.scheduler.jobs import AutomationJobs
from marketsentinel.storage.database import DatabaseManager

logger = get_logger("marketsentinel.scheduler.engine")
console = Console()


class AutomationScheduler:
    """Production scheduler orchestrating automated data ingestion, alerting, reporting, and backups."""

    def __init__(self, config: AppConfig, db: DatabaseManager | None = None) -> None:
        self.config = config
        self.db = db or DatabaseManager(
            db_path=config.storage.db_path, enable_wal=config.storage.enable_wal
        )
        self.jobs = AutomationJobs(config, self.db)
        self._is_running = False
        self._scheduler: BackgroundScheduler | BlockingScheduler | None = None

    def _job_listener(self, event: JobExecutionEvent) -> None:
        """Tracks job execution telemetry and records errors."""
        job_id = event.job_id
        if event.exception:
            logger.error(
                f"[bold red]Scheduled Task Error:[/bold red] Job '{job_id}' crashed with: {event.exception}"
            )
        else:
            logger.debug(f"Scheduled task '{job_id}' executed successfully.")

    def configure_scheduler(
        self, blocking: bool = False
    ) -> BackgroundScheduler | BlockingScheduler:
        """Initializes and schedules jobs according to application configuration."""
        scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
        scheduler = scheduler_cls(timezone="UTC")

        # 1. Ingestion Job (Every N seconds/minutes)
        ingest_sec = max(10, self.config.scheduler.ingestion_interval_seconds)
        scheduler.add_job(
            self.jobs.run_ingestion_and_indicators,
            trigger="interval",
            seconds=ingest_sec,
            id="job_ingestion",
            name="Market Ingestion & Indicators",
            replace_existing=True,
        )

        # 2. Alert Evaluation Job (runs shortly after ingestion)
        alert_sec = max(10, self.config.scheduler.alert_interval_seconds)
        scheduler.add_job(
            self.jobs.run_alert_evaluation,
            trigger="interval",
            seconds=alert_sec,
            id="job_alerts",
            name="Alert Rule Evaluation",
            replace_existing=True,
        )

        # 3. Daily Executive PDF Digest (Cron trigger e.g. at daily_report_time)
        time_parts = self.config.scheduler.daily_report_time.split(":")
        hour = int(time_parts[0]) if len(time_parts) > 0 else 18
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0

        scheduler.add_job(
            self.jobs.run_daily_digest_report,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="job_daily_report",
            name="Daily Executive PDF Digest",
            replace_existing=True,
        )

        # 4. Automated Backup Job (Every N hours)
        backup_hours = max(1, self.config.scheduler.backup_interval_hours)
        scheduler.add_job(
            self.jobs.run_automated_backup,
            trigger="interval",
            hours=backup_hours,
            id="job_backup",
            name="Automated Database Backup",
            replace_existing=True,
        )

        scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        self._scheduler = scheduler
        return scheduler

    def run_once(self) -> dict:
        """Executes a full synchronous single pass of all automated tasks."""
        logger.info("[bold cyan]Executing Full Single-Pass Automation Pipeline...[/bold cyan]")
        results = {
            "ingestion": self.jobs.run_ingestion_and_indicators(),
            "alerts": self.jobs.run_alert_evaluation(),
            "report": self.jobs.run_daily_digest_report(),
            "backup": self.jobs.run_automated_backup(),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        return results

    def start(self, blocking: bool = True, run_initial: bool = True) -> None:
        """Starts the autonomous scheduler loop.

        Args:
            blocking: If True, blocks the current thread until interrupted.
            run_initial: If True, runs an initial pass before entering interval loop.
        """
        scheduler = self.configure_scheduler(blocking=blocking)

        if run_initial:
            logger.info("Executing initial warm-up pipeline execution...")
            self.run_once()

        self._is_running = True
        logger.info("[bold green]MarketSentinel Autonomous Scheduler Activated.[/bold green]")
        self.print_schedule_dashboard()

        # Signal handlers for clean termination
        def handle_signal(sig, frame):
            logger.info("\nTermination signal received. Shutting down scheduler gracefully...")
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, handle_signal)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, handle_signal)
        except (ValueError, AttributeError):
            pass

        if blocking:
            try:
                scheduler.start()
            except (KeyboardInterrupt, SystemExit):
                self.stop()
        else:
            scheduler.start()

    def stop(self) -> None:
        """Gracefully halts all scheduler threads."""
        if self._scheduler and self._is_running:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception as e:
                logger.warning(f"Error during scheduler shutdown: {e}")
            self._is_running = False
            logger.info("MarketSentinel Scheduler stopped cleanly.")

    def print_schedule_dashboard(self) -> None:
        """Prints an interactive rich table detailing all scheduled recurring tasks."""
        table = Table(
            title="MarketSentinel — Autonomous Task Schedule",
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Task ID", style="bold white", width=18)
        table.add_column("Description", style="white", width=32)
        table.add_column("Trigger Cadence", style="green", width=22)
        table.add_column("Status", style="bold green", width=10)

        ingest_cadence = f"Every {self.config.scheduler.ingestion_interval_seconds}s"
        alert_cadence = f"Every {self.config.scheduler.alert_interval_seconds}s"
        report_cadence = f"Daily at {self.config.scheduler.daily_report_time} UTC"
        backup_cadence = f"Every {self.config.scheduler.backup_interval_hours}h"

        table.add_row("job_ingestion", "Market Ticker & Technical Ingestion", ingest_cadence, "ACTIVE")
        table.add_row("job_alerts", "Anomaly & Technical Alert Dispatch", alert_cadence, "ACTIVE")
        table.add_row("job_daily_report", "Executive PDF Risk Digest Generator", report_cadence, "ACTIVE")
        table.add_row("job_backup", "Encrypted Snapshot & Cloud Retention", backup_cadence, "ACTIVE")

        console.print(table)
