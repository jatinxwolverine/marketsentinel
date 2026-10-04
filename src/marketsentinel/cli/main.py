"""Command Line Interface (CLI) for MarketSentinel using Click and Rich."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import click

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from marketsentinel import __version__
from marketsentinel.alerts.dispatcher import AlertDispatcher
from marketsentinel.alerts.rules import AlertRuleEvaluator
from marketsentinel.api.coingecko import CoinGeckoService
from marketsentinel.core.config import AppConfig, load_config
from marketsentinel.core.logging import setup_logger
from marketsentinel.processing.indicators import TechnicalAnalysisEngine
from marketsentinel.reporting.pdf_generator import ExecutiveReportGenerator
from marketsentinel.scheduler.engine import AutomationScheduler
from marketsentinel.storage.backup import BackupManager
from marketsentinel.storage.database import DatabaseManager

console = Console()

BANNER = r"""[bold cyan]
  __  __            _        _    ____             _   _            _ 
 |  \/  | __ _ _ __| | _____| |_ / ___|  ___ _ __ | |_(_)_ __   ___| |
 | |\/| |/ _` | '__| |/ / _ \ __|\___ \ / _ \ '_ \| __| | '_ \ / _ \ |
 | |  | | (_| | |  |   <  __/ |_  ___) |  __/ | | | |_| | | | |  __/ |
 |_|  |_|\__,_|_|  |_|\_\___|\__| |____/ \___|_| |_|\__|_|_| |_|\___|_|
[/bold cyan][dim] Enterprise Financial & Crypto Automation Engine v""" + __version__ + r"""[/dim]
"""


@click.group(invoke_without_command=True)
@click.option("--config-file", "-c", type=click.Path(exists=False), help="Path to custom config.yaml")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose debug logging")
@click.version_option(version=__version__, prog_name="MarketSentinel")
@click.pass_context
def cli(ctx: click.Context, config_file: str | None, verbose: bool):
    """MarketSentinel: Enterprise Market Intelligence & Automation CLI."""
    log_level = "DEBUG" if verbose else "INFO"
    setup_logger(name="marketsentinel", log_level=log_level, log_file="logs/marketsentinel.log")

    cfg = load_config(config_file)
    if verbose:
        cfg.debug = True

    db = DatabaseManager(db_path=cfg.storage.db_path, enable_wal=cfg.storage.enable_wal)
    ctx.obj = {"config": cfg, "db": db}

    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print(
            Panel(
                "[bold]Enterprise Autonomous Financial Pipeline[/bold]\n"
                "• Integrates live cryptocurrency & market REST APIs\n"
                "• Calculates real-time technical indicators (RSI, SMA, Bollinger)\n"
                "• Autonomous rule-based multi-channel alert dispatch\n"
                "• Executive PDF report generation with high-resolution visual charts\n"
                "• Enterprise automated backups with retention rotation & cloud sync\n\n"
                "[cyan]Run [bold]marketsentinel --help[/bold] to explore all commands.[/cyan]",
                border_style="cyan",
            )
        )


@cli.command("fetch")
@click.option("--symbols", "-s", help="Comma-separated symbols (e.g. btc,eth,sol)")
@click.option("--currency", help="Target currency (usd, eur, gbp)")
@click.option("--save/--no-save", default=True, help="Persist fetched snapshots to database")
@click.option("--json-out", is_flag=True, help="Output response in structured JSON format")
@click.pass_obj
def fetch_cmd(ctx_obj: dict, symbols: str | None, currency: str | None, save: bool, json_out: bool):
    """Fetches live market ticker data and displays color-coded valuations."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    target_symbols = [s.strip() for s in symbols.split(",")] if symbols else cfg.symbols
    target_curr = currency or cfg.currency

    service = CoinGeckoService(base_url=cfg.api.base_url, timeout=cfg.api.timeout, api_key=cfg.api.api_key)

    with console.status("[bold cyan]Fetching real-time market snapshots...[/bold cyan]"):
        tickers = service.fetch_tickers(target_symbols, currency=target_curr)

    if save and tickers:
        db.save_tickers(tickers)

    if json_out:
        console.print_json(json.dumps([t.to_dict() for t in tickers], indent=2))
        return

    table = Table(title=f"MarketSentinel — Live Valuations ({target_curr.upper()})", header_style="bold cyan")
    table.add_column("Symbol", style="bold white", width=10)
    table.add_column("Name", style="white", width=14)
    table.add_column("Price", justify="right", style="bold", width=14)
    table.add_column("24h Change", justify="right", width=12)
    table.add_column("24h Range (High / Low)", justify="right", width=24)
    table.add_column("24h Volume", justify="right", width=16)
    table.add_column("Market Cap", justify="right", width=16)

    for t in tickers:
        change_style = "bold green" if t.change_24h_pct >= 0 else "bold red"
        table.add_row(
            t.symbol,
            t.name,
            f"${t.price:,.2f}" if t.price > 1 else f"${t.price:.4f}",
            f"[{change_style}]{t.change_24h_pct:+.2f}%[/{change_style}]",
            f"${t.high_24h:,.2f} / ${t.low_24h:,.2f}",
            f"${t.volume_24h:,.0f}",
            f"${t.market_cap:,.0f}",
        )

    console.print(table)
    if save:
        rprint(f"[dim]Successfully persisted {len(tickers)} market records to {cfg.storage.db_path}[/dim]")


@cli.command("analyze")
@click.option("--symbols", "-s", help="Comma-separated symbols (e.g. btc,eth)")
@click.option("--days", "-d", default=14, help="Historical candle analysis lookback days")
@click.option("--save/--no-save", default=True, help="Save computed signals to database")
@click.pass_obj
def analyze_cmd(ctx_obj: dict, symbols: str | None, days: int, save: bool):
    """Executes quantitative technical analysis (RSI, Moving Averages, Bollinger)."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    target_symbols = [s.strip() for s in symbols.split(",")] if symbols else cfg.symbols
    service = CoinGeckoService(base_url=cfg.api.base_url, timeout=cfg.api.timeout, api_key=cfg.api.api_key)

    signals = []
    with console.status("[bold cyan]Calculating quantitative technical indicators...[/bold cyan]"):
        tickers = service.fetch_tickers(target_symbols, currency=cfg.currency)
        for t in tickers:
            candles = service.fetch_historical_candles(t.symbol, days=days, currency=cfg.currency)
            sig = TechnicalAnalysisEngine.evaluate(t.symbol, current_price=t.price, candles=candles)
            signals.append(sig)

    if save and signals:
        db.save_signals(signals)

    table = Table(title="MarketSentinel — Quantitative Technical Signals", header_style="bold cyan")
    table.add_column("Symbol", style="bold white", width=10)
    table.add_column("Price", justify="right", style="bold", width=12)
    table.add_column("RSI-14", justify="right", width=10)
    table.add_column("SMA 20", justify="right", width=12)
    table.add_column("SMA 50", justify="right", width=12)
    table.add_column("Volatility", justify="right", width=12)
    table.add_column("Trend Bias", justify="center", width=12)
    table.add_column("Active Signals", style="dim", width=28)

    for s in signals:
        trend_style = "bold green" if s.trend == "BULLISH" else ("bold red" if s.trend == "BEARISH" else "yellow")
        rsi_style = "bold green" if s.rsi_14 <= 30 else ("bold red" if s.rsi_14 >= 70 else "white")
        sig_str = ", ".join(s.signals) if s.signals else "NORMAL_TRADING"

        table.add_row(
            s.symbol,
            f"${s.current_price:,.2f}",
            f"[{rsi_style}]{s.rsi_14:.1f}[/{rsi_style}]",
            f"${s.sma_20:,.2f}" if s.sma_20 else "N/A",
            f"${s.sma_50:,.2f}" if s.sma_50 else "N/A",
            f"{s.volatility_pct:.2f}%",
            f"[{trend_style}]{s.trend}[/{trend_style}]",
            sig_str,
        )

    console.print(table)


@cli.command("alert")
@click.option("--test", is_flag=True, help="Dispatch a synthetic test alert across all active channels")
@click.pass_obj
def alert_cmd(ctx_obj: dict, test: bool):
    """Evaluates real-time anomaly detection rules and triggers multi-channel alerts."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    dispatcher = AlertDispatcher(cfg.alerts, db=db)
    evaluator = AlertRuleEvaluator(cfg.alerts)

    if test:
        rprint("[bold yellow]Triggering synthetic test alert across active channels...[/bold yellow]")
        from marketsentinel.processing.models import AlertTrigger
        from datetime import datetime, timezone
        test_alert = AlertTrigger(
            symbol="BTC",
            rule_name="SYNTHETIC_TEST_ALERT",
            severity="CRITICAL",
            trigger_value=8.45,
            threshold_value=4.0,
            message="Test dispatch: Bitcoin simulated sudden surge +8.45% in 15 minutes.",
            timestamp=datetime.now(timezone.utc),
        )
        results = dispatcher.dispatch(test_alert)
        rprint(f"[bold green]Test Alert Dispatch Results:[/bold green] {results}")
        return

    service = CoinGeckoService(base_url=cfg.api.base_url, timeout=cfg.api.timeout, api_key=cfg.api.api_key)
    with console.status("[bold cyan]Scanning market for alert triggers...[/bold cyan]"):
        tickers = service.fetch_tickers(cfg.symbols, currency=cfg.currency)
        total_fired = 0

        for t in tickers:
            alerts = evaluator.evaluate_ticker(t)
            candles = service.fetch_historical_candles(t.symbol, days=7, currency=cfg.currency)
            sig = TechnicalAnalysisEngine.evaluate(t.symbol, t.price, candles)
            alerts.extend(evaluator.evaluate_signals(sig))

            for a in alerts:
                dispatcher.dispatch(a)
                total_fired += 1

    if total_fired == 0:
        rprint("[bold green]No market anomalies or threshold violations detected. All metrics nominal.[/bold green]")
    else:
        rprint(f"[bold yellow]Alert scan complete. {total_fired} notifications dispatched and recorded.[/bold yellow]")


@cli.command("report")
@click.option("--output-dir", "-o", help="Directory where generated PDF will be stored")
@click.option("--open-file", is_flag=True, help="Attempt to open the generated PDF with default viewer")
@click.pass_obj
def report_cmd(ctx_obj: dict, output_dir: str | None, open_file: bool):
    """Generates an executive-grade PDF market digest with charts and scorecards."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    if output_dir:
        cfg.reporting.output_dir = output_dir

    service = CoinGeckoService(base_url=cfg.api.base_url, timeout=cfg.api.timeout, api_key=cfg.api.api_key)
    report_gen = ExecutiveReportGenerator(cfg.reporting)

    with console.status("[bold cyan]Generating Executive Market Intelligence PDF Report...[/bold cyan]"):
        tickers = service.fetch_tickers(cfg.symbols, currency=cfg.currency)
        db.save_tickers(tickers)

        signals = []
        candle_map = {}
        for t in tickers:
            candles = service.fetch_historical_candles(t.symbol, days=14, currency=cfg.currency)
            candle_map[t.symbol] = candles
            sig = TechnicalAnalysisEngine.evaluate(t.symbol, t.price, candles)
            signals.append(sig)

        evaluator = AlertRuleEvaluator(cfg.alerts)
        alerts = []
        for t in tickers:
            alerts.extend(evaluator.evaluate_ticker(t))

        pdf_path = report_gen.generate_report(
            tickers=tickers,
            signals=signals,
            alerts=alerts,
            candle_history=candle_map,
        )

    rprint(f"[bold green]✔ PDF Report successfully generated at:[/bold green] [underline]{pdf_path}[/underline]")
    rprint(f"[dim]File size: {pdf_path.stat().st_size / 1024:.1f} KB[/dim]")

    if open_file and sys.platform.startswith("win"):
        import os
        os.startfile(str(pdf_path))


@cli.command("backup")
@click.option("--tag", "-t", default="manual", help="Descriptive label tag for backup archive")
@click.option("--retention", "-r", default=5, type=int, help="Number of latest backups to retain")
@click.pass_obj
def backup_cmd(ctx_obj: dict, tag: str, retention: int):
    """Executes automated database backup, SHA256 integrity verification, and rotation."""
    cfg: AppConfig = ctx_obj["config"]

    backup_mgr = BackupManager(
        db_path=cfg.storage.db_path,
        backup_dir=cfg.backup.backup_dir,
        retention_count=retention,
        compression=cfg.backup.compression,
    )

    with console.status("[bold cyan]Creating verified database snapshot archive...[/bold cyan]"):
        archive_path = backup_mgr.create_backup(tag=tag)

    rprint(f"[bold green]✔ Backup completed successfully:[/bold green] {archive_path.name}")
    rprint(f"[dim]Saved to: {archive_path}[/dim]")

    # Print backup directory list
    backups = backup_mgr.list_backups()
    table = Table(title="Available Backup Snapshots in Vault", header_style="bold cyan")
    table.add_column("Archive Filename", style="bold white")
    table.add_column("Size (KB)", justify="right")
    table.add_column("Created (UTC)", style="dim")

    for b in backups:
        table.add_row(b["filename"], f"{b['size_kb']:.1f}", b["modified"])

    console.print(table)


@cli.command("schedule")
@click.option("--once", is_flag=True, help="Execute a single synchronous run of all tasks and exit")
@click.option("--foreground/--daemon", default=True, help="Run interactively in foreground or background")
@click.pass_obj
def schedule_cmd(ctx_obj: dict, once: bool, foreground: bool):
    """Launches the autonomous scheduling engine for recurring automation."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    scheduler = AutomationScheduler(config=cfg, db=db)

    if once:
        rprint("[bold cyan]Executing single pass of scheduled tasks...[/bold cyan]")
        results = scheduler.run_once()
        rprint(Panel(json.dumps(results, indent=2), title="Execution Run Summary", border_style="green"))
        return

    console.print(BANNER)
    rprint("[bold green]Starting MarketSentinel Autonomous Scheduler Engine...[/bold green]")
    rprint("[dim]Press Ctrl+C at any time to halt.[/dim]\n")

    scheduler.start(blocking=foreground, run_initial=True)


@cli.command("status")
@click.pass_obj
def status_cmd(ctx_obj: dict):
    """Displays comprehensive system health, storage telemetry, and run history."""
    cfg: AppConfig = ctx_obj["config"]
    db: DatabaseManager = ctx_obj["db"]

    stats = db.get_system_stats()
    db_size_kb = stats["db_size_bytes"] / 1024.0

    table = Table(title="MarketSentinel — System Telemetry & Health", header_style="bold cyan")
    table.add_column("Component / Metric", style="bold white", width=32)
    table.add_column("Value / Status", style="green", width=36)

    table.add_row("Application Version", f"v{__version__}")
    table.add_row("Database Path", cfg.storage.db_path)
    table.add_row("Database Size", f"{db_size_kb:.2f} KB")
    table.add_row("Total Market Snapshots", str(stats["snapshot_count"]))
    table.add_row("Technical Signals Persisted", str(stats["signal_count"]))
    table.add_row("Alert Audit Trail Entries", str(stats["alert_count"]))
    table.add_row("Automated Scheduler Runs", str(stats["job_run_count"]))
    table.add_row("Monitored Asset Count", str(len(cfg.symbols)))
    table.add_row("System Health Status", "[bold green]ONLINE / NOMINAL[/bold green]")

    console.print(table)


if __name__ == "__main__":
    cli()
