"""
run_agent.py — CLI entry point for StocksAgent V2.

Usage:
    python tools/run_agent.py AAPL
    python tools/run_agent.py MSFT GOOGL TSLA

V2: Uses LangGraph state machine for orchestration.
"""

import os
import sys
import time
import argparse
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from tools.graph import run_graph


def print_banner():
    banner = """
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   📈  S T O C K S   A G E N T   V 2                 ║
║                                                      ║
║   AI-Powered Stock Analysis & Forecasting            ║
║   LangGraph + Multi-Step Reasoning + Quality Loop    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""
    print(banner)


def analyze_ticker(ticker: str) -> str:
    """Run the full LangGraph pipeline for a single ticker."""
    ticker = ticker.upper().strip()
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  Starting V2 analysis for: {ticker}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Run the LangGraph pipeline
    final_state = run_graph(ticker)

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Check for errors
    if final_state.get("error"):
        print(f"\n❌ Analysis failed for {ticker}: {final_state['error']}")
        return None

    pdf_path = final_state.get("pdf_path")
    analysis = final_state.get("analysis", {})
    technicals = final_state.get("technicals", {})
    critique = final_state.get("critique", {})

    # Summary
    recommendation = analysis.get("investment_recommendation", {})
    forecast = analysis.get("price_forecast", {})
    price = technicals.get("current_price", "?")
    rating = recommendation.get("rating", "N/A")
    validation = final_state.get("validation_issues", [])

    print(f"\n{'='*60}")
    print(f"  ✅ Analysis complete for {ticker}!")
    print(f"  📄 Report: {pdf_path}")
    print(f"  ⏱️  Time: {minutes}m {seconds}s")
    print(f"\n  💰 Current Price: ${price}")
    print(f"  📊 Rating: {rating}")
    print(f"  🧐 Critic Confidence: {critique.get('adjusted_confidence', 'N/A')}")
    print(f"  ✔️  Validation: {'PASSED' if not validation else f'{len(validation)} issues'}")

    # Token usage
    token_usage = analysis.get("_token_usage", {})
    critic_tokens = critique.get("_token_usage", {}).get("total_tokens", 0)
    total_tokens = token_usage.get("total_tokens", 0) + critic_tokens
    print(f"  🔢 Total tokens: {total_tokens} (~${total_tokens * 0.000005:.4f})")

    for period, label in [("1_year", "1Y"), ("3_year", "3Y"), ("5_year", "5Y")]:
        pf = forecast.get(period, {})
        bull = pf.get("bull", "?")
        base = pf.get("base", "?")
        bear = pf.get("bear", "?")
        print(f"  🎯 {label}: Bear=${bear} | Base=${base} | Bull=${bull}")

    print(f"{'='*60}\n")

    return pdf_path


def main():
    parser = argparse.ArgumentParser(
        description="StocksAgent V2 — AI-Powered Stock Analysis with LangGraph",
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
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found!")
        print("   Create a .env file in the project root with:")
        print("   OPENAI_API_KEY=sk-your-key-here")
        sys.exit(1)

    results = []
    for ticker in args.tickers:
        try:
            pdf_path = analyze_ticker(ticker)
            results.append((ticker, pdf_path, pdf_path is not None))
        except Exception as e:
            print(f"\n❌ Unexpected error for {ticker}: {e}")
            results.append((ticker, None, False))

    # Multi-ticker summary
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
