"""
run_agent.py — Main CLI orchestrator for the StocksAgent.

Usage:
    python tools/run_agent.py AAPL
    python tools/run_agent.py MSFT GOOGL TSLA   (multiple tickers)

This script orchestrates the full analysis pipeline:
1. Fetch stock data (price history + fundamentals)
2. Identify and analyze competitors
3. Fetch recent news
4. Fetch sector performance data
5. Run technical analysis (indicators + chart)
6. Send everything to GPT-4o for deep analysis
7. Generate PDF report
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Add project root to path so imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from tools.fetch_stock_data import fetch_stock_data
from tools.fetch_competitors import fetch_competitors
from tools.fetch_news import fetch_news
from tools.fetch_sector_data import fetch_sector_data
from tools.analyze_technical import analyze_technical
from tools.analyze_with_llm import analyze_with_llm
from tools.generate_pdf import generate_pdf


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   📈  S T O C K S   A G E N T                       ║
║                                                      ║
║   AI-Powered Stock Analysis & Forecasting            ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""
    print(banner)


def analyze_ticker(ticker: str) -> str:
    """Run the full analysis pipeline for a single ticker. Returns path to PDF."""
    ticker = ticker.upper().strip()
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  Starting analysis for: {ticker}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Ensure .tmp directory exists
    tmp_dir = os.path.join(PROJECT_ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    # ────────────────────────────────────────────
    # STEP 1: Fetch Stock Data
    # ────────────────────────────────────────────
    print("\n📊 Step 1/7: Fetching stock data...")
    try:
        stock_data = fetch_stock_data(ticker)
    except Exception as e:
        print(f"❌ Failed to fetch stock data: {e}")
        print("   Make sure the ticker is valid (e.g., AAPL, MSFT, GOOGL)")
        raise SystemExit(1)

    company_info = stock_data["info"]
    print(f"   ✓ {company_info['name']} | {company_info['sector']} | {company_info['industry']}")

    # ────────────────────────────────────────────
    # STEP 2: Fetch Competitors
    # ────────────────────────────────────────────
    print("\n🏢 Step 2/7: Identifying competitors...")
    try:
        competitors = fetch_competitors(ticker, company_info, stock_data["financials"])
    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch competitors: {e}")
        competitors = []

    # ────────────────────────────────────────────
    # STEP 3: Fetch News
    # ────────────────────────────────────────────
    print("\n📰 Step 3/7: Fetching recent news...")
    try:
        news = fetch_news(ticker)
    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch news: {e}")
        news = []

    # ────────────────────────────────────────────
    # STEP 4: Fetch Sector Data
    # ────────────────────────────────────────────
    print("\n📈 Step 4/7: Analyzing sector performance...")
    try:
        sector_data = fetch_sector_data(company_info.get("sector", "Unknown"))
    except Exception as e:
        print(f"⚠️  Warning: Failed to fetch sector data: {e}")
        sector_data = {"sector": company_info.get("sector", "Unknown"), "returns": {}, "spy_returns": {}}

    # ────────────────────────────────────────────
    # STEP 5: Technical Analysis
    # ────────────────────────────────────────────
    print("\n📉 Step 5/7: Running technical analysis...")
    try:
        technicals = analyze_technical(ticker, stock_data["history"], tmp_dir)
    except Exception as e:
        print(f"⚠️  Warning: Technical analysis failed: {e}")
        technicals = {"current_price": stock_data["financials"].get("current_price")}

    # ────────────────────────────────────────────
    # STEP 6: LLM Analysis
    # ────────────────────────────────────────────
    print("\n🤖 Step 6/7: Sending data to GPT-4o for analysis...")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-..."):
        print("❌ Error: OPENAI_API_KEY not set in .env file!")
        print("   Create a .env file with: OPENAI_API_KEY=sk-your-key-here")
        raise SystemExit(1)

    try:
        analysis = analyze_with_llm(
            ticker, stock_data, competitors, news, sector_data, technicals
        )
    except Exception as e:
        print(f"❌ Failed to get LLM analysis: {e}")
        raise SystemExit(1)

    # ────────────────────────────────────────────
    # STEP 7: Generate PDF
    # ────────────────────────────────────────────
    print("\n📄 Step 7/7: Generating PDF report...")
    try:
        pdf_path = generate_pdf(
            ticker, stock_data, competitors, sector_data, technicals, analysis, PROJECT_ROOT
        )
    except Exception as e:
        print(f"❌ Failed to generate PDF: {e}")
        raise SystemExit(1)

    # ────────────────────────────────────────────
    # DONE
    # ────────────────────────────────────────────
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'='*60}")
    print(f"  ✅ Analysis complete for {ticker}!")
    print(f"  📄 Report: {pdf_path}")
    print(f"  ⏱️  Time: {minutes}m {seconds}s")

    # Quick summary
    recommendation = analysis.get("investment_recommendation", {})
    forecast = analysis.get("price_forecast", {})
    price = technicals.get("current_price", "?")
    rating = recommendation.get("rating", "N/A")

    print(f"\n  💰 Current Price: ${price}")
    print(f"  📊 Rating: {rating}")

    for period, label in [("1_year", "1Y"), ("3_year", "3Y"), ("5_year", "5Y")]:
        pf = forecast.get(period, {})
        base = pf.get("base", "?")
        print(f"  🎯 {label} Base Target: ${base}")

    print(f"{'='*60}\n")

    return pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="StocksAgent — AI-Powered Stock Analysis & Forecasting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/run_agent.py AAPL              # Analyze Apple
  python tools/run_agent.py MSFT GOOGL TSLA   # Analyze multiple tickers
        """
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="One or more stock tickers to analyze (e.g., AAPL MSFT GOOGL)"
    )

    args = parser.parse_args()

    print_banner()

    # Validate env
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found!")
        print("   Create a .env file in the project root with:")
        print("   OPENAI_API_KEY=sk-your-key-here")
        sys.exit(1)

    results = []
    for ticker in args.tickers:
        try:
            pdf_path = analyze_ticker(ticker)
            results.append((ticker, pdf_path, True))
        except SystemExit:
            results.append((ticker, None, False))
        except Exception as e:
            print(f"\n❌ Unexpected error for {ticker}: {e}")
            results.append((ticker, None, False))

    # Final summary for multiple tickers
    if len(args.tickers) > 1:
        print(f"\n{'='*60}")
        print(f"  Summary — {len(results)} tickers processed")
        print(f"{'='*60}")
        for ticker, path, success in results:
            status = "✅" if success else "❌"
            print(f"  {status} {ticker}: {path or 'FAILED'}")
        print()


if __name__ == "__main__":
    main()
