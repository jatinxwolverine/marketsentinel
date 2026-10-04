"""Tests for Matplotlib charting and ReportLab executive PDF generation."""

from pathlib import Path
import pytest
from marketsentinel.api.fallbacks import generate_fallback_candles, generate_fallback_ticker
from marketsentinel.core.config import ReportingConfig
from marketsentinel.processing.indicators import TechnicalAnalysisEngine
from marketsentinel.reporting.charting import FinancialChartGenerator
from marketsentinel.reporting.pdf_generator import ExecutiveReportGenerator


def test_chart_generation(tmp_path):
    chart_dir = tmp_path / "charts"
    engine = FinancialChartGenerator(output_dir=str(chart_dir))

    tickers = [
        generate_fallback_ticker("bitcoin"),
        generate_fallback_ticker("ethereum"),
        generate_fallback_ticker("solana"),
    ]
    bar_chart = engine.plot_market_performance_bars(tickers)
    assert bar_chart.exists()
    assert bar_chart.stat().st_size > 0

    candles = generate_fallback_candles("bitcoin", days=7)
    ind_chart = engine.plot_price_and_indicators("BTC", candles=candles, rsi=48.0, sma_20=64000.0)
    assert ind_chart.exists()
    assert ind_chart.stat().st_size > 0


def test_executive_pdf_report_generation(tmp_path):
    report_dir = tmp_path / "reports"
    cfg = ReportingConfig(
        output_dir=str(report_dir),
        company_name="Test Capital Corp",
        title="Automated Test Risk Report",
        include_charts=True,
    )
    generator = ExecutiveReportGenerator(config=cfg)

    tickers = [
        generate_fallback_ticker("bitcoin"),
        generate_fallback_ticker("ethereum"),
        generate_fallback_ticker("solana"),
    ]
    signals = [
        TechnicalAnalysisEngine.evaluate(t.symbol, t.price, generate_fallback_candles(t.symbol, days=7))
        for t in tickers
    ]
    candle_map = {
        t.symbol: generate_fallback_candles(t.symbol, days=7) for t in tickers
    }

    pdf_path = generator.generate_report(
        tickers=tickers,
        signals=signals,
        alerts=[],
        candle_history=candle_map,
    )

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.stat().st_size > 5000  # Multi-page PDF with embedded charts
