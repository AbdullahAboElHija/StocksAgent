"""
fetch_sector_data.py — Fetches sector/industry performance data.

Usage:
    from tools.fetch_sector_data import fetch_sector_data
    sector = fetch_sector_data("Technology")

Returns a dict with sector ETF performance and trend data.
"""

import sys
import yfinance as yf
import pandas as pd


# Sector to ETF mapping (SPDR Select Sector ETFs)
SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Information Technology": "XLK",
    "Healthcare": "XLV",
    "Health Care": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Defensive": "XLP",
    "Consumer Staples": "XLP",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
    "Basic Materials": "XLB",
}

# Fallback: S&P 500
DEFAULT_ETF = "SPY"


def fetch_sector_data(sector: str) -> dict:
    """Fetch sector performance data using sector ETFs."""
    print(f"[fetch_sector_data] Analyzing sector: {sector}...")

    etf_ticker = SECTOR_ETF_MAP.get(sector, None)
    if not etf_ticker:
        print(f"[fetch_sector_data] No ETF mapping for '{sector}', using S&P 500 (SPY) as reference.")
        etf_ticker = DEFAULT_ETF

    etf = yf.Ticker(etf_ticker)
    info = etf.info

    # Fetch 5 years of history
    history = etf.history(period="5y", interval="1wk")

    # Calculate returns over different periods
    returns = {}
    if len(history) >= 2:
        current_price = history["Close"].iloc[-1]

        # Various lookback periods
        periods = {
            "1_month": 4,     # ~4 weeks
            "3_months": 13,   # ~13 weeks
            "6_months": 26,   # ~26 weeks
            "1_year": 52,     # ~52 weeks
            "3_years": 156,   # ~156 weeks
            "5_years": 260,   # ~260 weeks
        }

        for period_name, weeks in periods.items():
            if len(history) > weeks:
                past_price = history["Close"].iloc[-weeks]
                pct_return = ((current_price - past_price) / past_price) * 100
                returns[period_name] = round(pct_return, 2)
            else:
                returns[period_name] = None

    # Also fetch S&P 500 for comparison
    spy = yf.Ticker("SPY")
    spy_history = spy.history(period="5y", interval="1wk")
    spy_returns = {}
    if len(spy_history) >= 2:
        spy_current = spy_history["Close"].iloc[-1]
        for period_name, weeks in {"1_year": 52, "3_years": 156, "5_years": 260}.items():
            if len(spy_history) > weeks:
                spy_past = spy_history["Close"].iloc[-weeks]
                spy_returns[period_name] = round(((spy_current - spy_past) / spy_past) * 100, 2)

    result = {
        "sector": sector,
        "etf_ticker": etf_ticker,
        "etf_name": info.get("longName", info.get("shortName", etf_ticker)),
        "current_price": info.get("regularMarketPrice", info.get("previousClose")),
        "returns": returns,
        "spy_returns": spy_returns,
        "52_week_high": info.get("fiftyTwoWeekHigh"),
        "52_week_low": info.get("fiftyTwoWeekLow"),
    }

    print(f"[fetch_sector_data] Done. ETF: {etf_ticker} | 1Y return: {returns.get('1_year', 'N/A')}%")
    return result


if __name__ == "__main__":
    sector = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Technology"
    data = fetch_sector_data(sector)

    print(f"\n{'='*60}")
    print(f"  Sector: {data['sector']} ({data['etf_ticker']})")
    print(f"{'='*60}")
    print(f"  ETF: {data['etf_name']}")
    print(f"  Price: ${data['current_price']}")
    print(f"\n  Sector Returns:")
    for period, ret in data['returns'].items():
        print(f"    {period:>12s}: {ret:>8.2f}%" if ret else f"    {period:>12s}: N/A")
    print(f"\n  S&P 500 Returns (comparison):")
    for period, ret in data['spy_returns'].items():
        print(f"    {period:>12s}: {ret:>8.2f}%" if ret else f"    {period:>12s}: N/A")
