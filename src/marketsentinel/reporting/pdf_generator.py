"""Executive PDF Report Generator built with ReportLab."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from marketsentinel.core.config import ReportingConfig
from marketsentinel.core.exceptions import ReportGenerationError
from marketsentinel.core.logging import get_logger
from marketsentinel.processing.models import (
    AlertTrigger,
    CandlePoint,
    TechnicalSignals,
    TickerData,
)
from marketsentinel.reporting.charting import FinancialChartGenerator

logger = get_logger("marketsentinel.reporting.pdf")


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic running footers with 'Page X of Y' numbering."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(HexColor("#64748B"))

        # Running Top Header Rule
        self.setStrokeColor(HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, letter[1] - 40, letter[0] - 40, letter[1] - 40)
        self.drawString(40, letter[1] - 35, "MarketSentinel — Automated Portfolio Intelligence & Risk Digest")

        # Running Footer
        self.line(40, 42, letter[0] - 40, 42)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 40, 30, page_text)
        self.drawString(
            40,
            30,
            "CONFIDENTIAL & PROPRIETARY — Generated automatically by MarketSentinel Engine.",
        )
        self.restoreState()


class ExecutiveReportGenerator:
    """Compiles market data, technical indicators, alerts, and charts into an executive PDF."""

    def __init__(self, config: ReportingConfig) -> None:
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.chart_engine = FinancialChartGenerator(
            output_dir=str(self.output_dir / "charts")
        )

    def generate_report(
        self,
        tickers: list[TickerData],
        signals: list[TechnicalSignals],
        alerts: list[AlertTrigger] | None = None,
        candle_history: dict[str, list[CandlePoint]] | None = None,
    ) -> Path:
        """Assembles and generates the full multi-page PDF executive report."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"market_digest_{timestamp}.pdf"
        pdf_path = self.output_dir / filename

        try:
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=letter,
                leftMargin=40,
                rightMargin=40,
                topMargin=50,
                bottomMargin=50,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "DocTitle",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=HexColor("#0F172A"),
            )
            subtitle_style = ParagraphStyle(
                "DocSubTitle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=HexColor("#64748B"),
            )
            section_header = ParagraphStyle(
                "SectionHeader",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                textColor=HexColor("#1E293B"),
                spaceBefore=12,
                spaceAfter=6,
            )
            cell_bold = ParagraphStyle(
                "CellBold",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=10,
                textColor=HexColor("#0F172A"),
            )
            cell_normal = ParagraphStyle(
                "CellNormal",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10,
                textColor=HexColor("#334155"),
            )
            cell_green = ParagraphStyle(
                "CellGreen",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=HexColor("#16A34A"),
            )
            cell_red = ParagraphStyle(
                "CellRed",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=HexColor("#DC2626"),
            )

            story = []

            # 1. Header Banner
            report_time_str = datetime.now(timezone.utc).strftime("%B %d, %Y - %H:%M:%S UTC")
            header_table_data = [
                [
                    Paragraph(f"<b>{self.config.company_name}</b><br/>{self.config.title}", title_style),
                    Paragraph(f"<b>Automated Run:</b><br/>{report_time_str}<br/><b>Status:</b> Active Monitored", subtitle_style),
                ]
            ]
            header_table = Table(header_table_data, colWidths=[330, 200])
            header_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(header_table)
            story.append(Spacer(1, 10))
            story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor("#0284C7"), spaceAfter=14))

            # 2. Executive KPI Summary Cards
            total_cap = sum(t.market_cap for t in tickers)
            avg_change = sum(t.change_24h_pct for t in tickers) / len(tickers) if tickers else 0.0
            top_gainer = max(tickers, key=lambda t: t.change_24h_pct, default=None)
            top_loser = min(tickers, key=lambda t: t.change_24h_pct, default=None)

            kpi_data = [
                [
                    Paragraph("<b>Total Monitored Cap</b>", subtitle_style),
                    Paragraph("<b>Average 24h Change</b>", subtitle_style),
                    Paragraph("<b>Top Performer</b>", subtitle_style),
                    Paragraph("<b>Risk / Lagging</b>", subtitle_style),
                ],
                [
                    Paragraph(f"${total_cap:,.0f}", title_style),
                    Paragraph(f"{avg_change:+.2f}%", cell_green if avg_change >= 0 else cell_red),
                    Paragraph(f"<b>{top_gainer.symbol if top_gainer else 'N/A'}</b> ({top_gainer.change_24h_pct:+.2f}%)" if top_gainer else "N/A", cell_green),
                    Paragraph(f"<b>{top_loser.symbol if top_loser else 'N/A'}</b> ({top_loser.change_24h_pct:+.2f}%)" if top_loser else "N/A", cell_red),
                ],
            ]
            kpi_table = Table(kpi_data, colWidths=[130, 130, 135, 135])
            kpi_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(kpi_table)
            story.append(Spacer(1, 14))

            # 3. Market Overview Table
            story.append(Paragraph("1. Market Snapshot & Valuations", section_header))
            overview_rows = [
                [
                    Paragraph("<b>Asset</b>", cell_bold),
                    Paragraph("<b>Price (USD)</b>", cell_bold),
                    Paragraph("<b>24h Change</b>", cell_bold),
                    Paragraph("<b>24h High</b>", cell_bold),
                    Paragraph("<b>24h Low</b>", cell_bold),
                    Paragraph("<b>24h Volume</b>", cell_bold),
                    Paragraph("<b>Market Cap</b>", cell_bold),
                ]
            ]
            for t in tickers:
                change_style = cell_green if t.change_24h_pct >= 0 else cell_red
                overview_rows.append(
                    [
                        Paragraph(f"<b>{t.symbol}</b> ({t.name})", cell_normal),
                        Paragraph(f"${t.price:,.2f}" if t.price > 1 else f"${t.price:.4f}", cell_bold),
                        Paragraph(f"{t.change_24h_pct:+.2f}%", change_style),
                        Paragraph(f"${t.high_24h:,.2f}", cell_normal),
                        Paragraph(f"${t.low_24h:,.2f}", cell_normal),
                        Paragraph(f"${t.volume_24h:,.0f}", cell_normal),
                        Paragraph(f"${t.market_cap:,.0f}", cell_normal),
                    ]
                )

            overview_table = Table(overview_rows, colWidths=[95, 75, 65, 75, 75, 75, 75])
            overview_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0F172A")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
                        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            # Fix text color for header in TableStyle
            for col_idx in range(7):
                header_p = overview_rows[0][col_idx]
                header_p.style.textColor = HexColor("#FFFFFF")

            story.append(overview_table)
            story.append(Spacer(1, 14))

            # 4. Charts Section
            if self.config.include_charts:
                story.append(Paragraph("2. Performance Analytics & Indicator Visualizations", section_header))

                # Chart 1: Bar performance
                perf_chart_path = self.chart_engine.plot_market_performance_bars(tickers)
                if perf_chart_path.exists():
                    story.append(Image(str(perf_chart_path), width=7.2 * inch, height=2.6 * inch))
                    story.append(Spacer(1, 8))

                # Chart 2: Primary asset indicators chart (e.g. BTC)
                primary_symbol = tickers[0].symbol if tickers else "BTC"
                primary_candles = (candle_history or {}).get(primary_symbol, [])
                primary_signal = next((s for s in signals if s.symbol == primary_symbol), None)

                ind_chart_path = self.chart_engine.plot_price_and_indicators(
                    symbol=primary_symbol,
                    candles=primary_candles,
                    rsi=primary_signal.rsi_14 if primary_signal else 50.0,
                    sma_20=primary_signal.sma_20 if primary_signal else None,
                    sma_50=primary_signal.sma_50 if primary_signal else None,
                )
                if ind_chart_path.exists():
                    story.append(Image(str(ind_chart_path), width=7.2 * inch, height=3.6 * inch))
                    story.append(Spacer(1, 12))

            # 5. Technical Signals Table
            story.append(Paragraph("3. Technical Indicators & Quantitative Signals", section_header))
            sig_rows = [
                [
                    Paragraph("<b>Asset</b>", cell_bold),
                    Paragraph("<b>Current Price</b>", cell_bold),
                    Paragraph("<b>RSI (14)</b>", cell_bold),
                    Paragraph("<b>SMA 20</b>", cell_bold),
                    Paragraph("<b>SMA 50</b>", cell_bold),
                    Paragraph("<b>Volatility</b>", cell_bold),
                    Paragraph("<b>Trend Bias</b>", cell_bold),
                    Paragraph("<b>Triggered Signals</b>", cell_bold),
                ]
            ]
            for s in signals:
                trend_color = cell_green if s.trend == "BULLISH" else (cell_red if s.trend == "BEARISH" else cell_normal)
                rsi_display = f"{s.rsi_14:.1f}"
                sig_list_str = ", ".join(s.signals[:2]) if s.signals else "NORMAL_TRADING"
                sig_rows.append(
                    [
                        Paragraph(f"<b>{s.symbol}</b>", cell_bold),
                        Paragraph(f"${s.current_price:,.2f}", cell_normal),
                        Paragraph(rsi_display, cell_bold),
                        Paragraph(f"${s.sma_20:,.2f}" if s.sma_20 else "N/A", cell_normal),
                        Paragraph(f"${s.sma_50:,.2f}" if s.sma_50 else "N/A", cell_normal),
                        Paragraph(f"{s.volatility_pct:.2f}%", cell_normal),
                        Paragraph(s.trend, trend_color),
                        Paragraph(sig_list_str, cell_normal),
                    ]
                )

            sig_table = Table(sig_rows, colWidths=[55, 65, 50, 65, 65, 60, 60, 110])
            sig_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#1E293B")),
                        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F8FAFC")]),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            for col_idx in range(8):
                sig_rows[0][col_idx].style.textColor = HexColor("#FFFFFF")

            story.append(sig_table)
            story.append(Spacer(1, 14))

            # 6. Active Triggered Alerts Table
            if alerts:
                story.append(Paragraph("4. Automated Real-Time Risk & Opportunity Triggers", section_header))
                alert_rows = [
                    [
                        Paragraph("<b>Asset</b>", cell_bold),
                        Paragraph("<b>Rule</b>", cell_bold),
                        Paragraph("<b>Severity</b>", cell_bold),
                        Paragraph("<b>Trigger Details</b>", cell_bold),
                        Paragraph("<b>Timestamp (UTC)</b>", cell_bold),
                    ]
                ]
                for a in alerts[:10]:
                    sev_style = cell_red if a.severity == "CRITICAL" else cell_normal
                    alert_rows.append(
                        [
                            Paragraph(f"<b>{a.symbol}</b>", cell_bold),
                            Paragraph(a.rule_name, cell_normal),
                            Paragraph(a.severity, sev_style),
                            Paragraph(a.message, cell_normal),
                            Paragraph(a.timestamp.strftime("%H:%M:%S"), cell_normal),
                        ]
                    )
                alert_table = Table(alert_rows, colWidths=[50, 110, 60, 240, 70])
                alert_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#334155")),
                            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#FEF2F2")]),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                for col_idx in range(5):
                    alert_rows[0][col_idx].style.textColor = HexColor("#FFFFFF")
                story.append(alert_table)

            # Build document
            doc.build(story, canvasmaker=NumberedCanvas)
            logger.info(f"[bold green]Executive PDF Report Generated:[/bold green] {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise ReportGenerationError(f"PDF generation failed: {e}") from e
