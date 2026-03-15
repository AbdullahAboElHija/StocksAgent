"""
graph.py — LangGraph state machine for the StocksAgent V2 pipeline.

Defines the analysis graph with:
- Parallel data collection (competitors, news, sector)
- Sequential 4-step LLM analysis chain
- Quality validation with retry loop
- Critic review
"""

import os
import sys
import operator
from typing import TypedDict, Optional, Annotated
from langgraph.graph import StateGraph, END

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from tools.fetch_stock_data import fetch_stock_data
from tools.fetch_competitors import fetch_competitors
from tools.fetch_news import fetch_news
from tools.fetch_sector_data import fetch_sector_data
from tools.analyze_technical import analyze_technical
from tools.analyze_with_llm import analyze_with_llm
from tools.critic import critique_analysis
from tools.validator import validate_analysis, format_issues_for_reprompt
from tools.generate_pdf import generate_pdf


# ─── State Schema ──────────────────────────────────────────────────────


class AgentState(TypedDict):
    """Shared state for the entire pipeline."""
    # Input
    ticker: str

    # Data collection results
    stock_data: Optional[dict]
    competitors: Optional[list]
    news: Optional[list]
    sector_data: Optional[dict]
    technicals: Optional[dict]

    # Analysis
    analysis: Optional[dict]
    critique: Optional[dict]

    # Validation
    validation_issues: Optional[list]
    retry_count: int

    # Output
    pdf_path: Optional[str]
    error: Optional[str]


# ─── Node Functions ────────────────────────────────────────────────────


def node_fetch_stock(state: AgentState) -> dict:
    """Fetch core stock data — must run first."""
    ticker = state["ticker"]
    print(f"\n📊 [Node] Fetching stock data for {ticker}...")
    try:
        stock_data = fetch_stock_data(ticker)
        info = stock_data["info"]
        print(f"   ✓ {info['name']} | {info['sector']} | {info['industry']}")
        return {"stock_data": stock_data}
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return {"error": f"Failed to fetch stock data: {e}"}


def node_fetch_competitors(state: AgentState) -> dict:
    """Fetch competitor data. Depends on stock_data."""
    ticker = state["ticker"]
    stock_data = state["stock_data"]
    print(f"\n🏢 [Node] Identifying competitors for {ticker}...")
    try:
        competitors = fetch_competitors(ticker, stock_data["info"], stock_data["financials"])
        return {"competitors": competitors}
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
        return {"competitors": []}


def node_fetch_news(state: AgentState) -> dict:
    """Fetch recent news. Independent after stock_data."""
    ticker = state["ticker"]
    print(f"\n📰 [Node] Fetching news for {ticker}...")
    try:
        news = fetch_news(ticker)
        return {"news": news}
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
        return {"news": []}


def node_fetch_sector(state: AgentState) -> dict:
    """Fetch sector data. Independent after stock_data."""
    stock_data = state["stock_data"]
    sector = stock_data["info"].get("sector", "Unknown")
    print(f"\n📈 [Node] Analyzing sector: {sector}...")
    try:
        sector_data = fetch_sector_data(sector)
        return {"sector_data": sector_data}
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
        return {"sector_data": {"sector": sector, "returns": {}, "spy_returns": {}}}


def node_technical_analysis(state: AgentState) -> dict:
    """Run technical analysis. Depends on stock_data."""
    ticker = state["ticker"]
    stock_data = state["stock_data"]
    print(f"\n📉 [Node] Running technical analysis for {ticker}...")
    tmp_dir = os.path.join(PROJECT_ROOT, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    try:
        technicals = analyze_technical(ticker, stock_data["history"], tmp_dir)
        return {"technicals": technicals}
    except Exception as e:
        print(f"   ⚠️ Warning: {e}")
        return {"technicals": {"current_price": stock_data["financials"].get("current_price")}}


def node_llm_analysis(state: AgentState) -> dict:
    """Run the 4-step LLM analysis chain."""
    ticker = state["ticker"]
    print(f"\n🤖 [Node] Running 4-step LLM analysis for {ticker}...")
    try:
        analysis = analyze_with_llm(
            ticker,
            state["stock_data"],
            state.get("competitors", []),
            state.get("news", []),
            state.get("sector_data", {}),
            state.get("technicals", {}),
        )
        return {"analysis": analysis}
    except Exception as e:
        print(f"   ❌ LLM analysis failed: {e}")
        return {"error": f"LLM analysis failed: {e}"}


def node_validate(state: AgentState) -> dict:
    """Validate the analysis output."""
    analysis = state.get("analysis", {})
    current_price = state.get("technicals", {}).get("current_price", 0) or 0
    retry_count = state.get("retry_count", 0)

    print(f"\n🔍 [Node] Validating analysis (attempt {retry_count + 1})...")
    issues = validate_analysis(analysis, current_price)

    if issues:
        print(f"   ⚠️ Found {len(issues)} issues:")
        for issue in issues:
            print(f"     - {issue}")
    else:
        print(f"   ✓ All checks passed!")

    return {"validation_issues": issues, "retry_count": retry_count + 1}


def node_critic(state: AgentState) -> dict:
    """Have a senior PM critique the analysis."""
    ticker = state["ticker"]
    analysis = state.get("analysis", {})
    current_price = state.get("technicals", {}).get("current_price", 0) or 0

    print(f"\n🧐 [Node] Senior PM reviewing analysis for {ticker}...")
    try:
        critique = critique_analysis(ticker, analysis, current_price)
        return {"critique": critique}
    except Exception as e:
        print(f"   ⚠️ Critic failed: {e}")
        return {"critique": {"overall_assessment": "Critic review unavailable.", "error": str(e)}}


def node_generate_pdf(state: AgentState) -> dict:
    """Generate the final PDF report."""
    ticker = state["ticker"]
    print(f"\n📄 [Node] Generating PDF report for {ticker}...")
    try:
        pdf_path = generate_pdf(
            ticker,
            state["stock_data"],
            state.get("competitors", []),
            state.get("sector_data", {}),
            state.get("technicals", {}),
            state.get("analysis", {}),
            PROJECT_ROOT,
            critique=state.get("critique"),
        )
        return {"pdf_path": pdf_path}
    except Exception as e:
        print(f"   ❌ PDF generation failed: {e}")
        return {"error": f"PDF generation failed: {e}"}


# ─── Conditional Edges ─────────────────────────────────────────────────


def should_retry_or_continue(state: AgentState) -> str:
    """After validation, decide whether to retry LLM or proceed to critic."""
    issues = state.get("validation_issues", [])
    retry_count = state.get("retry_count", 0)

    # Filter for critical issues only (not thin sections or missing reasoning)
    critical_issues = [i for i in issues if any(
        tag in i for tag in ["ORDER_ERROR", "NEGATIVE_PRICE", "UNREALISTIC", "MISSING_FORECAST", "MATH_ERROR", "FLAT_BASE"]
    )]

    if critical_issues and retry_count < 3:
        print(f"   🔄 Critical issues found. Retrying LLM analysis (attempt {retry_count + 1}/3)...")
        return "retry"
    else:
        if critical_issues:
            print(f"   ⚠️ Max retries reached. Proceeding with best result.")
        return "continue"


def check_for_error(state: AgentState) -> str:
    """Check if there's a fatal error after stock data fetch."""
    if state.get("error"):
        return "error"
    return "continue"


# ─── Build the Graph ───────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Construct the LangGraph state machine."""

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("fetch_stock", node_fetch_stock)
    graph.add_node("fetch_competitors", node_fetch_competitors)
    graph.add_node("fetch_news", node_fetch_news)
    graph.add_node("fetch_sector", node_fetch_sector)
    graph.add_node("technical_analysis", node_technical_analysis)
    graph.add_node("llm_analysis", node_llm_analysis)
    graph.add_node("validate", node_validate)
    graph.add_node("critic", node_critic)
    graph.add_node("generate_pdf", node_generate_pdf)

    # Entry point
    graph.set_entry_point("fetch_stock")

    # After fetch_stock: check for error, then fan out to parallel nodes
    graph.add_conditional_edges(
        "fetch_stock",
        check_for_error,
        {"error": END, "continue": "fetch_competitors"}
    )

    # Sequential after stock data (LangGraph will run them in order)
    # In practice these are fast enough; true parallelism would need async
    graph.add_edge("fetch_competitors", "fetch_news")
    graph.add_edge("fetch_news", "fetch_sector")
    graph.add_edge("fetch_sector", "technical_analysis")

    # After all data collected → LLM analysis
    graph.add_edge("technical_analysis", "llm_analysis")

    # After LLM → validate
    graph.add_edge("llm_analysis", "validate")

    # After validate → retry or continue
    graph.add_conditional_edges(
        "validate",
        should_retry_or_continue,
        {"retry": "llm_analysis", "continue": "critic"}
    )

    # After critic → generate PDF
    graph.add_edge("critic", "generate_pdf")

    # PDF → END
    graph.add_edge("generate_pdf", END)

    return graph.compile()


def run_graph(ticker: str) -> dict:
    """Run the full analysis graph for a ticker. Returns the final state."""
    graph = build_graph()

    initial_state = {
        "ticker": ticker.upper().strip(),
        "stock_data": None,
        "competitors": None,
        "news": None,
        "sector_data": None,
        "technicals": None,
        "analysis": None,
        "critique": None,
        "validation_issues": None,
        "retry_count": 0,
        "pdf_path": None,
        "error": None,
    }

    final_state = graph.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/graph.py <TICKER>")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    result = run_graph(sys.argv[1])
    if result.get("error"):
        print(f"\n❌ Error: {result['error']}")
    else:
        print(f"\n✅ Done: {result.get('pdf_path')}")
