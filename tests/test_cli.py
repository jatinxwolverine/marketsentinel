"""Tests for Click CLI command execution and options handling."""

from click.testing import CliRunner
import pytest
from marketsentinel.cli.main import cli


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_cli_help(cli_runner):
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "MarketSentinel" in result.output
    assert "fetch" in result.output
    assert "analyze" in result.output
    assert "report" in result.output
    assert "schedule" in result.output


def test_cli_fetch(cli_runner, tmp_path):
    config_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "cli_test.db"
    config_file.write_text(
        f"""
storage:
  db_path: "{db_file.as_posix()}"
symbols:
  - "bitcoin"
        """,
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["-c", str(config_file), "fetch", "--symbols", "btc", "--currency", "usd"])
    assert result.exit_code == 0
    assert "BTC" in result.output


def test_cli_analyze(cli_runner, tmp_path):
    config_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "cli_test.db"
    config_file.write_text(f'storage:\n  db_path: "{db_file.as_posix()}"\n', encoding="utf-8")

    result = cli_runner.invoke(cli, ["-c", str(config_file), "analyze", "--symbols", "btc", "--days", "7"])
    assert result.exit_code == 0
    assert "RSI-14" in result.output or "Trend" in result.output


def test_cli_alert_test(cli_runner, tmp_path):
    config_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "cli_test.db"
    config_file.write_text(f'storage:\n  db_path: "{db_file.as_posix()}"\n', encoding="utf-8")

    result = cli_runner.invoke(cli, ["-c", str(config_file), "alert", "--test"])
    assert result.exit_code == 0
    assert "Test Alert Dispatch Results" in result.output


def test_cli_backup(cli_runner, tmp_path):
    config_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "cli_test.db"
    backup_dir = tmp_path / "cli_backups"
    config_file.write_text(
        f"""
storage:
  db_path: "{db_file.as_posix()}"
backup:
  backup_dir: "{backup_dir.as_posix()}"
        """,
        encoding="utf-8",
    )

    from marketsentinel.storage.database import DatabaseManager
    from marketsentinel.api.fallbacks import generate_fallback_ticker
    db = DatabaseManager(db_path=str(db_file), enable_wal=False)
    db.save_tickers([generate_fallback_ticker("bitcoin")])

    result = cli_runner.invoke(cli, ["-c", str(config_file), "backup", "--tag", "testrun"])
    assert result.exit_code == 0
    assert "Backup completed successfully" in result.output


def test_cli_status(cli_runner, tmp_path):
    config_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "cli_test.db"
    config_file.write_text(f'storage:\n  db_path: "{db_file.as_posix()}"\n', encoding="utf-8")

    result = cli_runner.invoke(cli, ["-c", str(config_file), "status"])
    assert result.exit_code == 0
    assert "System Telemetry & Health" in result.output
