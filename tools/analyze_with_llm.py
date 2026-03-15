"""
analyze_with_llm.py — Sends all collected data to OpenAI for comprehensive analysis.

Usage:
    from tools.analyze_with_llm import analyze_with_llm
    analysis = analyze_with_llm(ticker, stock_data, competitors, news, sector_data, technicals)

Returns a dict with structured analysis sections.
"""

import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def _format_financials_for_prompt(financials: dict) -> str:
    """Format financial metrics into a readable string for the LLM."""
    lines = []

    def fmt_num(val, prefix="$", suffix=""):
        if val is None:
            return "N/A"
        if isinstance(val, (int, float)):
            if abs(val) >= 1e12:
                return f"{prefix}{val/1e12:.2f}T{suffix}"
            if abs(val) >= 1e9:
                return f"{prefix}{val/1e9:.2f}B{suffix}"
            if abs(val) >= 1e6:
                return f"{prefix}{val/1e6:.2f}M{suffix}"
            return f"{prefix}{val:,.2f}{suffix}"
        return str(val)

    def fmt_pct(val):
        if val is None:
            return "N/A"
        return f"{val*100:.2f}%" if abs(val) < 1 else f"{val:.2f}%"

    lines.append(f"Market Cap: {fmt_num(financials.get('market_cap'))}")
    lines.append(f"Current Price: {fmt_num(financials.get('current_price'))}")
    lines.append(f"52W High: {fmt_num(financials.get('52_week_high'))} | 52W Low: {fmt_num(financials.get('52_week_low'))}")
    lines.append(f"P/E (trailing): {financials.get('pe_trailing', 'N/A')} | P/E (forward): {financials.get('pe_forward', 'N/A')}")
    lines.append(f"PEG Ratio: {financials.get('peg_ratio', 'N/A')}")
    lines.append(f"P/B: {financials.get('price_to_book', 'N/A')} | P/S: {financials.get('price_to_sales', 'N/A')}")
    lines.append(f"EV/EBITDA: {financials.get('ev_to_ebitda', 'N/A')}")
    lines.append(f"Profit Margin: {fmt_pct(financials.get('profit_margin'))}")
    lines.append(f"Operating Margin: {fmt_pct(financials.get('operating_margin'))}")
    lines.append(f"Gross Margin: {fmt_pct(financials.get('gross_margin'))}")
    lines.append(f"ROE: {fmt_pct(financials.get('roe'))} | ROA: {fmt_pct(financials.get('roa'))}")
    lines.append(f"Revenue Growth: {fmt_pct(financials.get('revenue_growth'))}")
    lines.append(f"Earnings Growth: {fmt_pct(financials.get('earnings_growth'))}")
    lines.append(f"Total Revenue: {fmt_num(financials.get('total_revenue'))}")
    lines.append(f"Net Income: {fmt_num(financials.get('net_income'))}")
    lines.append(f"EBITDA: {fmt_num(financials.get('ebitda'))}")
    lines.append(f"EPS (trailing): {financials.get('eps_trailing', 'N/A')} | EPS (forward): {financials.get('eps_forward', 'N/A')}")
    lines.append(f"Debt/Equity: {financials.get('debt_to_equity', 'N/A')}")
    lines.append(f"Current Ratio: {financials.get('current_ratio', 'N/A')}")
    lines.append(f"Total Cash: {fmt_num(financials.get('total_cash'))} | Total Debt: {fmt_num(financials.get('total_debt'))}")
    lines.append(f"Dividend Yield: {fmt_pct(financials.get('dividend_yield'))}")
    lines.append(f"Analyst Target (mean): {fmt_num(financials.get('target_mean'))} | Recommendation: {financials.get('recommendation', 'N/A')}")

    # Annual revenue/income history
    annual_rev = financials.get("annual_revenue", {})
    if annual_rev:
        lines.append(f"\nAnnual Revenue History:")
        for year, val in sorted(annual_rev.items(), reverse=True):
            lines.append(f"  {year}: {fmt_num(val)}")

    annual_ni = financials.get("annual_net_income", {})
    if annual_ni:
        lines.append(f"\nAnnual Net Income History:")
        for year, val in sorted(annual_ni.items(), reverse=True):
            lines.append(f"  {year}: {fmt_num(val)}")

    return "\n".join(lines)


def _format_competitors_for_prompt(competitors: list) -> str:
    """Format competitor data for the LLM prompt."""
    if not competitors:
        return "No competitor data available."

    lines = []
    for c in competitors:
        mcap = c.get('market_cap')
        mcap_str = f"${mcap/1e9:.1f}B" if mcap else "N/A"
        lines.append(f"\n--- {c['ticker']}: {c.get('name', 'Unknown')} ---")
        lines.append(f"  Market Cap: {mcap_str}")
        lines.append(f"  P/E: {c.get('pe_trailing', 'N/A')} | Forward P/E: {c.get('pe_forward', 'N/A')}")
        lines.append(f"  Revenue Growth: {c.get('revenue_growth', 'N/A')}")
        lines.append(f"  Profit Margin: {c.get('profit_margin', 'N/A')}")
        lines.append(f"  ROE: {c.get('roe', 'N/A')}")
        lines.append(f"  D/E: {c.get('debt_to_equity', 'N/A')}")
        lines.append(f"  Analyst Target: ${c.get('target_mean', 'N/A')}")

    return "\n".join(lines)


def _format_news_for_prompt(news: list) -> str:
    """Format news articles for the LLM prompt."""
    if not news:
        return "No recent news available."

    lines = []
    for i, article in enumerate(news[:15], 1):
        lines.append(f"{i}. [{article.get('published', 'N/A')}] {article.get('title', 'No title')}")
        lines.append(f"   Source: {article.get('publisher', 'Unknown')}")

    return "\n".join(lines)


def _format_sector_for_prompt(sector_data: dict) -> str:
    """Format sector data for the LLM prompt."""
    lines = []
    lines.append(f"Sector: {sector_data.get('sector', 'Unknown')}")
    lines.append(f"Sector ETF: {sector_data.get('etf_ticker', 'N/A')} ({sector_data.get('etf_name', '')})")

    returns = sector_data.get("returns", {})
    lines.append(f"\nSector Returns:")
    for period, ret in returns.items():
        lines.append(f"  {period}: {ret}%" if ret is not None else f"  {period}: N/A")

    spy_returns = sector_data.get("spy_returns", {})
    lines.append(f"\nS&P 500 (SPY) Returns for comparison:")
    for period, ret in spy_returns.items():
        lines.append(f"  {period}: {ret}%" if ret is not None else f"  {period}: N/A")

    return "\n".join(lines)


def _format_technicals_for_prompt(technicals: dict) -> str:
    """Format technical indicators for the LLM prompt."""
    lines = []
    lines.append(f"Current Price: ${technicals.get('current_price', 'N/A')}")
    lines.append(f"Trend: {technicals.get('trend', 'N/A')}")
    lines.append(f"SMA 50: ${technicals.get('sma_50', 'N/A')} | SMA 200: ${technicals.get('sma_200', 'N/A')}")
    lines.append(f"EMA 20: ${technicals.get('ema_20', 'N/A')}")
    lines.append(f"RSI (14): {technicals.get('rsi_14', 'N/A')} — {technicals.get('rsi_signal', 'N/A')}")
    lines.append(f"MACD: {technicals.get('macd', 'N/A')} | Signal: {technicals.get('macd_signal_line', 'N/A')} — {technicals.get('macd_interpretation', 'N/A')}")
    lines.append(f"Support: ${technicals.get('support', 'N/A')} | Resistance: ${technicals.get('resistance', 'N/A')}")
    lines.append(f"52W High: ${technicals.get('52_week_high', 'N/A')} | 52W Low: ${technicals.get('52_week_low', 'N/A')}")
    return "\n".join(lines)


def analyze_with_llm(
    ticker: str,
    stock_data: dict,
    competitors: list,
    news: list,
    sector_data: dict,
    technicals: dict,
) -> dict:
    """Send all collected data to OpenAI for comprehensive analysis and forecasting."""
    print(f"[analyze_with_llm] Sending data to GPT-4o for analysis of {ticker}...")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build the mega-prompt
    company_info = stock_data["info"]
    financials = stock_data["financials"]

    prompt = f"""You are a senior equity research analyst. Analyze the following stock comprehensively and provide a detailed investment report.

===== COMPANY =====
Name: {company_info.get('name', ticker)}
Ticker: {ticker}
Sector: {company_info.get('sector', 'Unknown')}
Industry: {company_info.get('industry', 'Unknown')}
Country: {company_info.get('country', 'Unknown')}

Description:
{company_info.get('description', 'N/A')[:1000]}

===== FINANCIAL METRICS =====
{_format_financials_for_prompt(financials)}

===== TECHNICAL ANALYSIS =====
{_format_technicals_for_prompt(technicals)}

===== COMPETITORS =====
{_format_competitors_for_prompt(competitors)}

===== SECTOR PERFORMANCE =====
{_format_sector_for_prompt(sector_data)}

===== RECENT NEWS =====
{_format_news_for_prompt(news)}

===== YOUR TASK =====

Provide a comprehensive analysis in the following JSON format. Be specific with numbers and reasoning. For price forecasts, provide actual dollar amounts based on your analysis of the fundamentals, technicals, sector trends, competitive position, and news sentiment.

{{
    "company_overview": "2-3 paragraphs about what the company does, its market position, and competitive advantages/moats",

    "fundamental_analysis": "3-4 paragraphs analyzing financial health, profitability, growth trajectory, valuation relative to peers, balance sheet strength",

    "technical_analysis_summary": "2-3 paragraphs interpreting the current technical setup, trend direction, key support/resistance levels, momentum indicators",

    "competitor_comparison": "2-3 paragraphs comparing the company against its peers on valuation, growth, margins, and market position. Who is stronger? Why?",

    "sector_outlook": "2-3 paragraphs on the sector/industry outlook for the next 1-5 years. What are the tailwinds and headwinds?",

    "news_sentiment": "1-2 paragraphs summarizing the recent news sentiment and how it may impact the stock",

    "price_forecast": {{
        "current_price": {technicals.get('current_price', 0)},
        "1_year": {{
            "bull": <price target>,
            "base": <price target>,
            "bear": <price target>,
            "reasoning": "Brief explanation of assumptions for each scenario"
        }},
        "3_year": {{
            "bull": <price target>,
            "base": <price target>,
            "bear": <price target>,
            "reasoning": "Brief explanation"
        }},
        "5_year": {{
            "bull": <price target>,
            "base": <price target>,
            "bear": <price target>,
            "reasoning": "Brief explanation"
        }}
    }},

    "risk_factors": [
        "Risk 1 with explanation",
        "Risk 2 with explanation",
        "Risk 3 with explanation",
        "Risk 4 with explanation",
        "Risk 5 with explanation"
    ],

    "investment_recommendation": {{
        "rating": "Strong Buy / Buy / Hold / Sell / Strong Sell",
        "summary": "2-3 sentences summarizing your overall recommendation and key thesis",
        "confidence": "High / Medium / Low"
    }}
}}

Important:
- Be data-driven. Reference specific numbers from the data provided.
- Price forecasts should be realistic, grounded in the company's growth rate, sector trends, and valuation multiples.
- Consider both upside catalysts and downside risks.
- The analysis should read like a professional equity research report.
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {
                "role": "system",
                "content": "You are a senior equity research analyst at a top-tier investment bank. Provide thorough, data-driven analysis. Always respond with valid JSON."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    try:
        analysis = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError as e:
        print(f"[analyze_with_llm] Warning: Failed to parse JSON response: {e}")
        # Try to salvage what we can
        analysis = {
            "company_overview": response.choices[0].message.content,
            "error": "Failed to parse structured response"
        }

    # Add token usage info
    usage = response.usage
    analysis["_token_usage"] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }

    print(f"[analyze_with_llm] Done. Used {usage.total_tokens} tokens.")
    return analysis


if __name__ == "__main__":
    print("This tool is meant to be called from run_agent.py")
    print("It requires all data to be collected first.")
