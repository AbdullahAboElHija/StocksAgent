"""
fetch_stock_data.py — Fetches historical price data and fundamentals via yfinance.

Usage:
    from tools.fetch_stock_data import fetch_stock_data
    data = fetch_stock_data("AAPL")

Returns a dict with keys:
    - info: company info (name, sector, industry, description, etc.)
    - history: DataFrame of 5 years daily OHLCV
    - financials: dict of key financial metrics
"""

import yfinance as yf
import pandas as pd
import sys
import json


def fetch_stock_data(ticker: str) -> dict:
    """Fetch comprehensive stock data for a given ticker."""
    print(f"[fetch_stock_data] Fetching data for {ticker}...")

    stock = yf.Ticker(ticker)

    # --- Company Info ---
    info = stock.info
    company_info = {
        "ticker": ticker,
        "name": info.get("longName", info.get("shortName", ticker)),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "description": info.get("longBusinessSummary", "N/A"),
        "website": info.get("website", "N/A"),
        "country": info.get("country", "N/A"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange", "N/A"),
    }

    # --- Historical Price Data (5 years, daily) ---
    print(f"[fetch_stock_data] Fetching 5Y price history...")
    history = stock.history(period="5y", interval="1d")

    # --- Key Financial Metrics ---
    print(f"[fetch_stock_data] Extracting financial metrics...")
    financials = {
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
        "previous_close": info.get("previousClose"),
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
        "50_day_avg": info.get("fiftyDayAverage"),
        "200_day_avg": info.get("twoHundredDayAverage"),
        "volume": info.get("volume"),
        "avg_volume": info.get("averageVolume"),
        # Valuation
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "peg_ratio": info.get("pegRatio"),
        "price_to_book": info.get("priceToBook"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        # Profitability
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "gross_margin": info.get("grossMargins"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        # Growth
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
        # Dividends
        "dividend_yield": info.get("dividendYield"),
        "dividend_rate": info.get("dividendRate"),
        "payout_ratio": info.get("payoutRatio"),
        # Financial Health
        "total_cash": info.get("totalCash"),
        "total_debt": info.get("totalDebt"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "quick_ratio": info.get("quickRatio"),
        # Revenue / Earnings
        "total_revenue": info.get("totalRevenue"),
        "revenue_per_share": info.get("revenuePerShare"),
        "ebitda": info.get("ebitda"),
        "net_income": info.get("netIncomeToCommon"),
        "eps_trailing": info.get("trailingEps"),
        "eps_forward": info.get("forwardEps"),
        # Analyst
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "target_mean": info.get("targetMeanPrice"),
        "target_median": info.get("targetMedianPrice"),
        "recommendation": info.get("recommendationKey"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
    }

    # --- Historical Financials (annual) ---
    try:
        income_stmt = stock.financials
        if income_stmt is not None and not income_stmt.empty:
            annual_revenue = {}
            annual_net_income = {}
            for col in income_stmt.columns:
                year = str(col.year) if hasattr(col, 'year') else str(col)
                if "Total Revenue" in income_stmt.index:
                    val = income_stmt.loc["Total Revenue", col]
                    annual_revenue[year] = float(val) if pd.notna(val) else None
                if "Net Income" in income_stmt.index:
                    val = income_stmt.loc["Net Income", col]
                    annual_net_income[year] = float(val) if pd.notna(val) else None
            financials["annual_revenue"] = annual_revenue
            financials["annual_net_income"] = annual_net_income
    except Exception as e:
        print(f"[fetch_stock_data] Warning: Could not fetch income statement: {e}")
        financials["annual_revenue"] = {}
        financials["annual_net_income"] = {}

    result = {
        "info": company_info,
        "history": history,
        "financials": financials,
    }

    print(f"[fetch_stock_data] Done. Got {len(history)} days of price data for {company_info['name']}.")
    return result


def _format_number(val):
    """Format large numbers for display."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.2f}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_stock_data.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    data = fetch_stock_data(ticker)

    print(f"\n{'='*60}")
    print(f"  {data['info']['name']} ({ticker})")
    print(f"  Sector: {data['info']['sector']} | Industry: {data['info']['industry']}")
    print(f"{'='*60}")
    print(f"  Price: {_format_number(data['financials']['current_price'])}")
    print(f"  Market Cap: {_format_number(data['financials']['market_cap'])}")
    print(f"  P/E (trailing): {data['financials']['pe_trailing']}")
    print(f"  52W Range: {_format_number(data['financials']['52_week_low'])} - {_format_number(data['financials']['52_week_high'])}")
    print(f"  Analyst Target: {_format_number(data['financials']['target_mean'])}")
    print(f"  History: {len(data['history'])} daily records")
