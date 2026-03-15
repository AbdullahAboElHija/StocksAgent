"""
fetch_competitors.py — Identifies competitors via OpenAI and fetches their financial data.

Usage:
    from tools.fetch_competitors import fetch_competitors
    competitors = fetch_competitors("AAPL", company_info, financials)

Returns a list of dicts, each containing competitor ticker, name, and key metrics.
"""

import os
import sys
import json
import yfinance as yf
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def fetch_competitors(ticker: str, company_info: dict, financials: dict) -> list:
    """Identify top competitors and fetch their financial summaries."""
    print(f"[fetch_competitors] Identifying competitors for {ticker}...")

    # --- Step 1: Use OpenAI to identify competitors ---
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""You are a financial analyst. Given the following company, identify exactly 5 of its most relevant direct competitors that are publicly traded.

Company: {company_info.get('name', ticker)}
Ticker: {ticker}
Sector: {company_info.get('sector', 'Unknown')}
Industry: {company_info.get('industry', 'Unknown')}
Description: {company_info.get('description', 'N/A')[:500]}

Return ONLY a JSON array of objects with "ticker" and "name" fields. Example:
[{{"ticker": "MSFT", "name": "Microsoft Corporation"}}, ...]

Important:
- Only include companies that trade on major US exchanges (NYSE, NASDAQ)
- Pick the most direct competitors in the same industry
- Do NOT include {ticker} itself
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    try:
        resp_text = response.choices[0].message.content
        parsed = json.loads(resp_text)
        # Handle both {"competitors": [...]} and direct [...]
        if isinstance(parsed, dict):
            competitor_list = parsed.get("competitors", parsed.get("data", list(parsed.values())[0]))
        else:
            competitor_list = parsed
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[fetch_competitors] Warning: Could not parse LLM response: {e}")
        competitor_list = []

    # --- Step 2: Fetch financial data for each competitor ---
    print(f"[fetch_competitors] Found {len(competitor_list)} competitors. Fetching data...")
    competitors = []

    for comp in competitor_list[:5]:  # Cap at 5
        comp_ticker = comp.get("ticker", "").upper()
        comp_name = comp.get("name", comp_ticker)

        if not comp_ticker:
            continue

        try:
            stock = yf.Ticker(comp_ticker)
            info = stock.info

            competitor_data = {
                "ticker": comp_ticker,
                "name": info.get("longName", comp_name),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "current_price": info.get("currentPrice", info.get("regularMarketPrice")),
                "market_cap": info.get("marketCap"),
                "pe_trailing": info.get("trailingPE"),
                "pe_forward": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "dividend_yield": info.get("dividendYield"),
                "total_revenue": info.get("totalRevenue"),
                "eps_trailing": info.get("trailingEps"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                "recommendation": info.get("recommendationKey"),
                "target_mean": info.get("targetMeanPrice"),
            }

            competitors.append(competitor_data)
            print(f"  ✓ {comp_ticker}: {competitor_data['name']}")

        except Exception as e:
            print(f"  ✗ {comp_ticker}: Failed to fetch data ({e})")

    print(f"[fetch_competitors] Done. Got data for {len(competitors)} competitors.")
    return competitors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_competitors.py <TICKER>")
        sys.exit(1)

    from tools.fetch_stock_data import fetch_stock_data

    ticker = sys.argv[1].upper()
    stock_data = fetch_stock_data(ticker)
    competitors = fetch_competitors(ticker, stock_data["info"], stock_data["financials"])

    print(f"\n{'='*60}")
    print(f"  Competitors of {stock_data['info']['name']}")
    print(f"{'='*60}")
    for c in competitors:
        mcap = c['market_cap']
        mcap_str = f"${mcap/1e9:.1f}B" if mcap else "N/A"
        pe_str = f"{c['pe_trailing']:.1f}" if c['pe_trailing'] else "N/A"
        print(f"  {c['ticker']:6s} | {c['name'][:30]:30s} | MCap: {mcap_str:>10s} | P/E: {pe_str}")
