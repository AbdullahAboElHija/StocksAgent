"""
generate_pdf.py — Generates a professional PDF report from the analysis results.

Usage:
    from tools.generate_pdf import generate_pdf
    path = generate_pdf(ticker, stock_data, competitors, sector_data, technicals, analysis, output_dir)
"""

import os
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.colors import HexColor


# ─── Color Palette ───
DARK_BG = HexColor("#1a1a2e")
ACCENT_BLUE = HexColor("#0066cc")
ACCENT_CYAN = HexColor("#00b4d8")
DARK_GRAY = HexColor("#2d2d44")
LIGHT_GRAY = HexColor("#f0f0f5")
TEXT_DARK = HexColor("#1a1a1a")
TEXT_MEDIUM = HexColor("#4a4a5a")
GREEN = HexColor("#2ecc71")
RED = HexColor("#e74c3c")
YELLOW = HexColor("#f1c40f")
WHITE = colors.white


def _create_styles():
    """Create custom paragraph styles for the report."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=32,
        textColor=ACCENT_BLUE,
        alignment=TA_CENTER,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="CoverSubtitle",
        fontName="Helvetica",
        fontSize=14,
        textColor=TEXT_MEDIUM,
        alignment=TA_CENTER,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=ACCENT_BLUE,
        spaceBefore=20,
        spaceAfter=10,
        borderWidth=0,
        borderPadding=0,
    ))

    styles.add(ParagraphStyle(
        name="SubHeader",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=TEXT_DARK,
        spaceBefore=12,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="BodyText2",
        fontName="Helvetica",
        fontSize=10,
        textColor=TEXT_DARK,
        alignment=TA_JUSTIFY,
        spaceBefore=4,
        spaceAfter=4,
        leading=14,
    ))

    styles.add(ParagraphStyle(
        name="SmallText",
        fontName="Helvetica",
        fontSize=8,
        textColor=TEXT_MEDIUM,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=2,
    ))

    styles.add(ParagraphStyle(
        name="RatingBuy",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=GREEN,
        alignment=TA_CENTER,
        spaceBefore=10,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="RatingSell",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=RED,
        alignment=TA_CENTER,
        spaceBefore=10,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="RatingHold",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=YELLOW,
        alignment=TA_CENTER,
        spaceBefore=10,
        spaceAfter=6,
    ))

    return styles


def _fmt_num(val, prefix="$"):
    if val is None:
        return "N/A"
    if isinstance(val, str):
        return val
    if abs(val) >= 1e12:
        return f"{prefix}{val/1e12:.2f}T"
    if abs(val) >= 1e9:
        return f"{prefix}{val/1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"{prefix}{val/1e6:.2f}M"
    return f"{prefix}{val:,.2f}"


def _fmt_pct(val):
    if val is None:
        return "N/A"
    if isinstance(val, str):
        return val
    if abs(val) < 1:
        return f"{val*100:.1f}%"
    return f"{val:.1f}%"


def _get_rating_style(rating: str) -> str:
    """Return the appropriate style name for the investment rating."""
    rating_lower = rating.lower() if rating else ""
    if "buy" in rating_lower:
        return "RatingBuy"
    elif "sell" in rating_lower:
        return "RatingSell"
    return "RatingHold"


def generate_pdf(
    ticker: str,
    stock_data: dict,
    competitors: list,
    sector_data: dict,
    technicals: dict,
    analysis: dict,
    output_dir: str,
    critique: dict = None,
) -> str:
    """Generate the full PDF report."""
    print(f"[generate_pdf] Building PDF report for {ticker}...")

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{ticker}_Report_{today}.pdf"
    output_path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = _create_styles()
    story = []
    company_info = stock_data["info"]
    financials = stock_data["financials"]

    # ═══════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(ticker, styles["CoverTitle"]))
    story.append(Paragraph(company_info.get("name", ticker), styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="60%", thickness=2, color=ACCENT_BLUE, spaceAfter=10, spaceBefore=10))
    story.append(Paragraph("Stock Analysis Report — V2", styles["CoverSubtitle"]))
    story.append(Paragraph("Multi-Step Reasoning | Quality Validated | Peer Reviewed", styles["SmallText"]))
    story.append(Paragraph(f"Generated: {today}", styles["CoverSubtitle"]))
    story.append(Spacer(1, 0.5 * inch))

    # Quick stats on cover
    price = financials.get("current_price", 0)
    mcap = _fmt_num(financials.get("market_cap"))
    pe = financials.get("pe_trailing")
    pe_str = f"{pe:.1f}" if pe else "N/A"

    cover_data = [
        ["Current Price", "Market Cap", "P/E Ratio", "Sector"],
        [_fmt_num(price), mcap, pe_str, company_info.get("sector", "N/A")],
    ]
    cover_table = Table(cover_data, colWidths=[3.5 * cm] * 4)
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, 1), LIGHT_GRAY),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(cover_table)

    # Investment recommendation on cover
    recommendation = analysis.get("investment_recommendation", {})
    rating = recommendation.get("rating", "N/A")
    rating_style = _get_rating_style(rating)
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(f"Investment Rating: {rating}", styles[rating_style]))
    story.append(Paragraph(
        recommendation.get("summary", ""),
        styles["SmallText"]
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════
    # EXECUTIVE SUMMARY / COMPANY OVERVIEW
    # ═══════════════════════════════════════════
    story.append(Paragraph("1. Company Overview", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))
    overview = analysis.get("company_overview", "Analysis not available.")
    for para in overview.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # FUNDAMENTAL ANALYSIS
    # ═══════════════════════════════════════════
    story.append(Paragraph("2. Fundamental Analysis", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    # Key metrics table
    story.append(Paragraph("Key Financial Metrics", styles["SubHeader"]))
    metrics_data = [
        ["Metric", "Value", "Metric", "Value"],
        ["Market Cap", mcap, "Revenue", _fmt_num(financials.get("total_revenue"))],
        ["P/E (TTM)", pe_str, "Net Income", _fmt_num(financials.get("net_income"))],
        ["P/E (Fwd)", f"{financials.get('pe_forward', 'N/A')}", "EBITDA", _fmt_num(financials.get("ebitda"))],
        ["P/B Ratio", f"{financials.get('price_to_book', 'N/A')}", "EPS (TTM)", f"${financials.get('eps_trailing', 'N/A')}"],
        ["PEG Ratio", f"{financials.get('peg_ratio', 'N/A')}", "EPS (Fwd)", f"${financials.get('eps_forward', 'N/A')}"],
        ["Profit Margin", _fmt_pct(financials.get("profit_margin")), "ROE", _fmt_pct(financials.get("roe"))],
        ["Op. Margin", _fmt_pct(financials.get("operating_margin")), "ROA", _fmt_pct(financials.get("roa"))],
        ["D/E Ratio", f"{financials.get('debt_to_equity', 'N/A')}", "Current Ratio", f"{financials.get('current_ratio', 'N/A')}"],
        ["Div. Yield", _fmt_pct(financials.get("dividend_yield")), "Rev. Growth", _fmt_pct(financials.get("revenue_growth"))],
    ]
    metrics_table = Table(metrics_data, colWidths=[3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.15 * inch))

    # LLM fundamental commentary
    fundamental_text = analysis.get("fundamental_analysis", "")
    for para in fundamental_text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # TECHNICAL ANALYSIS
    # ═══════════════════════════════════════════
    story.append(Paragraph("3. Technical Analysis", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    # Embed chart image
    chart_path = technicals.get("chart_path")
    if chart_path and os.path.exists(chart_path):
        img = Image(chart_path, width=16 * cm, height=11 * cm)
        story.append(img)
        story.append(Spacer(1, 0.1 * inch))

    # Technical indicators table
    tech_data = [
        ["Indicator", "Value", "Signal"],
        ["Trend", technicals.get("trend", "N/A"), "—"],
        ["SMA 50", f"${technicals.get('sma_50', 'N/A')}", "Above" if (technicals.get("current_price", 0) or 0) > (technicals.get("sma_50", 0) or 0) else "Below"],
        ["SMA 200", f"${technicals.get('sma_200', 'N/A')}", "Above" if (technicals.get("current_price", 0) or 0) > (technicals.get("sma_200", 0) or 0) else "Below"],
        ["RSI (14)", f"{technicals.get('rsi_14', 'N/A')}", technicals.get("rsi_signal", "N/A")],
        ["MACD", f"{technicals.get('macd', 'N/A')}", technicals.get("macd_interpretation", "N/A")],
        ["Support", f"${technicals.get('support', 'N/A')}", "—"],
        ["Resistance", f"${technicals.get('resistance', 'N/A')}", "—"],
    ]
    tech_table = Table(tech_data, colWidths=[4 * cm, 4 * cm, 4 * cm])
    tech_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tech_table)
    story.append(Spacer(1, 0.1 * inch))

    # LLM tech commentary
    tech_text = analysis.get("technical_analysis_summary", "")
    for para in tech_text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(PageBreak())

    # ═══════════════════════════════════════════
    # COMPETITOR COMPARISON
    # ═══════════════════════════════════════════
    story.append(Paragraph("4. Competitor Comparison", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    if competitors:
        comp_header = ["Ticker", "Market Cap", "P/E", "Rev Growth", "Margin", "ROE"]
        comp_rows = [comp_header]

        # Add the main ticker first
        comp_rows.append([
            f"{ticker} ★",
            _fmt_num(financials.get("market_cap")),
            f"{financials.get('pe_trailing', 'N/A')}",
            _fmt_pct(financials.get("revenue_growth")),
            _fmt_pct(financials.get("profit_margin")),
            _fmt_pct(financials.get("roe")),
        ])

        for c in competitors:
            comp_rows.append([
                c.get("ticker", "?"),
                _fmt_num(c.get("market_cap")),
                f"{c.get('pe_trailing', 'N/A')}",
                _fmt_pct(c.get("revenue_growth")),
                _fmt_pct(c.get("profit_margin")),
                _fmt_pct(c.get("roe")),
            ])

        comp_table = Table(comp_rows, colWidths=[2.2 * cm, 2.8 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm, 2.2 * cm])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (-1, 1), HexColor("#e6f3ff")),  # Highlight main ticker
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 2), (-1, -1), [LIGHT_GRAY, WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 0.1 * inch))

    comp_text = analysis.get("competitor_comparison", "")
    for para in comp_text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # SECTOR OUTLOOK
    # ═══════════════════════════════════════════
    story.append(Paragraph("5. Sector Outlook", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    # Sector performance table
    returns = sector_data.get("returns", {})
    spy_returns = sector_data.get("spy_returns", {})
    sector_rows = [
        ["Period", f"{sector_data.get('etf_ticker', 'Sector')}", "S&P 500", "vs. Market"],
    ]
    for period in ["1_year", "3_years", "5_years"]:
        sector_ret = returns.get(period)
        spy_ret = spy_returns.get(period)
        diff = None
        if sector_ret is not None and spy_ret is not None:
            diff = sector_ret - spy_ret
        sector_rows.append([
            period.replace("_", " ").title(),
            f"{sector_ret:.1f}%" if sector_ret is not None else "N/A",
            f"{spy_ret:.1f}%" if spy_ret is not None else "N/A",
            f"{diff:+.1f}%" if diff is not None else "N/A",
        ])

    sector_table = Table(sector_rows, colWidths=[3.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm])
    sector_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(sector_table)
    story.append(Spacer(1, 0.1 * inch))

    sector_text = analysis.get("sector_outlook", "")
    for para in sector_text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # NEWS SENTIMENT
    # ═══════════════════════════════════════════
    story.append(Paragraph("6. News Sentiment", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    news_text = analysis.get("news_sentiment", "")
    for para in news_text.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["BodyText2"]))

    story.append(PageBreak())

    # ═══════════════════════════════════════════
    # PRICE FORECASTS
    # ═══════════════════════════════════════════
    story.append(Paragraph("7. Price Forecast", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    forecast = analysis.get("price_forecast", {})
    current = forecast.get("current_price", technicals.get("current_price", "N/A"))

    story.append(Paragraph(f"Current Price: ${current}", styles["SubHeader"]))
    story.append(Spacer(1, 0.1 * inch))

    # Forecast table
    forecast_header = ["Timeframe", "🐻 Bear Case", "📊 Base Case", "🐂 Bull Case"]
    forecast_rows = [forecast_header]

    for period, label in [("1_year", "1 Year"), ("3_year", "3 Years"), ("5_year", "5 Years")]:
        pf = forecast.get(period, {})
        forecast_rows.append([
            label,
            f"${pf.get('bear', 'N/A')}",
            f"${pf.get('base', 'N/A')}",
            f"${pf.get('bull', 'N/A')}",
        ])

    forecast_table = Table(forecast_rows, colWidths=[3 * cm, 3.8 * cm, 3.8 * cm, 3.8 * cm])
    forecast_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK_GRAY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (1, 1), (1, -1), HexColor("#fde8e8")),  # Bear = light red
        ("BACKGROUND", (2, 1), (2, -1), HexColor("#e8f4e8")),  # Base = light green
        ("BACKGROUND", (3, 1), (3, -1), HexColor("#e8f0fe")),  # Bull = light blue
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(forecast_table)
    story.append(Spacer(1, 0.15 * inch))

    # Forecast reasoning
    for period in ["1_year", "3_year", "5_year"]:
        pf = forecast.get(period, {})
        reasoning = pf.get("reasoning", "")
        if reasoning:
            period_label = period.replace("_", "-").title()
            story.append(Paragraph(f"<b>{period_label} Outlook:</b> {reasoning}", styles["BodyText2"]))
            story.append(Spacer(1, 0.05 * inch))

    # ── Math Breakdown Table (V2) ──
    math = analysis.get("math_breakdown", {})
    if math:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Valuation Math (EPS × P/E)", styles["SubHeader"]))

        math_header = ["Period", "Scenario", "EPS Growth", "Proj. EPS", "P/E", "Target"]
        math_rows = [math_header]

        for period, label in [("1_year", "1Y"), ("3_year", "3Y"), ("5_year", "5Y")]:
            pm = math.get(period, {})
            for scenario in ["bull", "base", "bear"]:
                sm = pm.get(scenario, {})
                if sm:
                    math_rows.append([
                        label,
                        scenario.title(),
                        f"{sm.get('eps_growth', 'N/A')}",
                        f"${sm.get('projected_eps', 'N/A')}",
                        f"{sm.get('assumed_pe', 'N/A')}x",
                        f"${sm.get('calculated_target', 'N/A')}",
                    ])

        if len(math_rows) > 1:
            math_table = Table(math_rows, colWidths=[1.8*cm, 2.2*cm, 2.5*cm, 2.5*cm, 2*cm, 2.5*cm])
            math_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), DARK_GRAY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(math_table)

    story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # CRITIC REVIEW (V2)
    # ═══════════════════════════════════════════
    if critique and not critique.get("error"):
        story.append(Paragraph("8. Senior PM Review", styles["SectionHeader"]))
        story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

        conf = critique.get("adjusted_confidence", "N/A")
        conf_style = "RatingBuy" if conf == "High" else ("RatingHold" if conf == "Medium" else "RatingSell")
        story.append(Paragraph(f"Reviewer Confidence: {conf}", styles[conf_style]))
        story.append(Spacer(1, 0.1 * inch))

        assessment = critique.get("overall_assessment", "")
        if assessment:
            story.append(Paragraph(assessment, styles["BodyText2"]))
            story.append(Spacer(1, 0.1 * inch))

        forecast_review = critique.get("forecast_review", "")
        if forecast_review:
            story.append(Paragraph("<b>Forecast Review:</b>", styles["SubHeader"]))
            story.append(Paragraph(forecast_review, styles["BodyText2"]))
            story.append(Spacer(1, 0.1 * inch))

        weaknesses = critique.get("weaknesses", [])
        if weaknesses:
            story.append(Paragraph("<b>Weaknesses Identified:</b>", styles["SubHeader"]))
            for w in weaknesses:
                story.append(Paragraph(f"• {w}", styles["BodyText2"]))

        missed = critique.get("missed_risks", [])
        if missed:
            story.append(Paragraph("<b>Additional Risks (from reviewer):</b>", styles["SubHeader"]))
            for m in missed:
                story.append(Paragraph(f"• {m}", styles["BodyText2"]))

        key_q = critique.get("key_question", "")
        if key_q:
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph(f"<b>Key Question for Investors:</b> {key_q}", styles["BodyText2"]))

        story.append(Spacer(1, 0.2 * inch))

    # ═══════════════════════════════════════════
    # RISK FACTORS
    # ═══════════════════════════════════════════
    section_num = "9" if critique and not critique.get("error") else "8"
    story.append(Paragraph(f"{section_num}. Risk Factors", styles["SectionHeader"]))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=8))

    risks = analysis.get("risk_factors", [])
    if isinstance(risks, list):
        for i, risk in enumerate(risks, 1):
            story.append(Paragraph(f"<b>{i}.</b> {risk}", styles["BodyText2"]))
    elif isinstance(risks, str):
        story.append(Paragraph(risks, styles["BodyText2"]))

    story.append(Spacer(1, 0.3 * inch))

    # ═══════════════════════════════════════════
    # DISCLAIMER
    # ═══════════════════════════════════════════
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))
    disclaimer = (
        "<b>Disclaimer:</b> This report is generated by an AI-powered analysis system and is for "
        "informational purposes only. It does not constitute financial advice, investment recommendations, "
        "or an offer to buy or sell securities. Price forecasts are based on AI reasoning using historical "
        "data, fundamental analysis, and market trends — they are NOT guaranteed predictions. Always "
        "consult with a qualified financial advisor before making investment decisions. Past performance "
        "does not guarantee future results."
    )
    story.append(Paragraph(disclaimer, styles["SmallText"]))

    # Token usage footnote
    token_usage = analysis.get("_token_usage", {})
    critic_tokens = 0
    if critique:
        critic_tokens = critique.get("_token_usage", {}).get("total_tokens", 0)
    total_tokens = token_usage.get("total_tokens", 0) + critic_tokens
    steps = token_usage.get("steps", 1)
    if total_tokens:
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph(
            f"StocksAgent V2 | {steps}-step analysis + critic review | "
            f"Tokens: {total_tokens} | Est. cost: ${total_tokens * 0.000005:.4f}",
            styles["SmallText"]
        ))

    # ─── BUILD PDF ───
    doc.build(story)
    print(f"[generate_pdf] ✓ Report saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    print("This tool is meant to be called from run_agent.py")
