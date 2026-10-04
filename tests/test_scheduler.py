"""Tests for APScheduler automation engine and task execution."""

from pathlib import Path
import pytest
from marketsentinel.core.config import AppConfig
from marketsentinel.scheduler.engine import AutomationScheduler
from marketsentinel.storage.database import DatabaseManager


def test_scheduler_job_registration(tmp_path):
    db_file = tmp_path / "scheduler_test.db"
    db = DatabaseManager(db_path=str(db_file), enable_wal=False)

    cfg = AppConfig()
    cfg.storage.db_path = str(db_file)
    cfg.reporting.output_dir = str(tmp_path / "reports")
    cfg.backup.backup_dir = str(tmp_path / "backups")

    scheduler = AutomationScheduler(config=cfg, db=db)
    sched = scheduler.configure_scheduler(blocking=False)

    job_ids = [job.id for job in sched.get_jobs()]
    assert "job_ingestion" in job_ids
    assert "job_alerts" in job_ids
    assert "job_daily_report" in job_ids
    assert "job_backup" in job_ids


def test_scheduler_run_once(tmp_path):
    from unittest.mock import patch
    from marketsentinel.api.fallbacks import generate_fallback_candles, generate_fallback_ticker

    db_file = tmp_path / "scheduler_run_once.db"
    db = DatabaseManager(db_path=str(db_file), enable_wal=False)

    cfg = AppConfig()
    cfg.storage.db_path = str(db_file)
    cfg.reporting.output_dir = str(tmp_path / "reports")
    cfg.backup.backup_dir = str(tmp_path / "backups")
    cfg.symbols = ["bitcoin", "ethereum"]

    scheduler = AutomationScheduler(config=cfg, db=db)

    # Mock external API to return deterministic fallback data instantaneously
    sample_tickers = [generate_fallback_ticker("bitcoin"), generate_fallback_ticker("ethereum")]
    sample_candles = generate_fallback_candles("bitcoin", days=7)

    with patch.object(scheduler.jobs.api_service, "fetch_tickers", return_value=sample_tickers), \
         patch.object(scheduler.jobs.api_service, "fetch_historical_candles", return_value=sample_candles):
        results = scheduler.run_once()

    assert results["ingestion"]["status"] == "SUCCESS"
    assert results["alerts"]["status"] == "SUCCESS"
    assert results["report"]["status"] == "SUCCESS"
    assert results["backup"]["status"] == "SUCCESS"

    stats = db.get_system_stats()
    assert stats["snapshot_count"] >= 2
    assert stats["signal_count"] >= 2
    assert stats["job_run_count"] >= 4
