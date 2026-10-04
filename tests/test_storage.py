"""Tests for database persistence and automated backup retention."""

from pathlib import Path
import pytest
from marketsentinel.api.fallbacks import generate_fallback_ticker
from marketsentinel.processing.indicators import TechnicalAnalysisEngine
from marketsentinel.storage.backup import BackupManager
from marketsentinel.storage.database import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_market.db"
    return DatabaseManager(db_path=str(db_file), enable_wal=False)


def test_database_initialization(temp_db):
    stats = temp_db.get_system_stats()
    assert stats["snapshot_count"] == 0
    assert stats["signal_count"] == 0
    assert stats["alert_count"] == 0


def test_save_and_retrieve_tickers(temp_db):
    tickers = [
        generate_fallback_ticker("bitcoin"),
        generate_fallback_ticker("ethereum"),
    ]
    saved_count = temp_db.save_tickers(tickers)
    assert saved_count == 2

    latest = temp_db.get_latest_tickers()
    assert len(latest) == 2
    symbols = [t.symbol for t in latest]
    assert "BTC" in symbols
    assert "ETH" in symbols


def test_save_and_retrieve_signals(temp_db):
    sig = TechnicalAnalysisEngine.evaluate("BTC", current_price=64000.0)
    saved = temp_db.save_signals([sig])
    assert saved == 1

    stats = temp_db.get_system_stats()
    assert stats["signal_count"] == 1


def test_record_scheduler_run(temp_db):
    temp_db.record_job_run(
        job_name="TEST_JOB",
        status="SUCCESS",
        duration_ms=45.2,
        details="Sample details",
    )
    stats = temp_db.get_system_stats()
    assert stats["job_run_count"] == 1


def test_backup_creation_and_retention(tmp_path):
    db_file = tmp_path / "test_backup.db"
    db = DatabaseManager(db_path=str(db_file), enable_wal=False)
    db.save_tickers([generate_fallback_ticker("solana")])

    backup_dir = tmp_path / "backups"
    backup_mgr = BackupManager(
        db_path=str(db_file),
        backup_dir=str(backup_dir),
        retention_count=2,
        compression="gz",
    )

    # Create 3 backups
    b1 = backup_mgr.create_backup(tag="run1")
    b2 = backup_mgr.create_backup(tag="run2")
    b3 = backup_mgr.create_backup(tag="run3")

    assert b3.exists()
    assert b3.stat().st_size > 0

    # With retention=2, the oldest backup (b1) should have been pruned
    remaining = backup_mgr.list_backups()
    assert len(remaining) == 2
    filenames = [b["filename"] for b in remaining]
    assert b3.name in filenames
    assert b2.name in filenames
    assert b1.name not in filenames
