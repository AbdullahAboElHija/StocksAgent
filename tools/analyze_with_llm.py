"""
analyze_with_llm.py — Multi-step LLM reasoning chain for stock analysis.

V2: Replaces single mega-prompt with 4 focused analysis steps:
  Step 1: Fundamental analysis
  Step 2: Technical analysis interpretation
  Step 3: Competitive & sector position
  Step 4: Price forecasting with explicit math (show your work)

Each step builds on the previous, producing deeper and more rigorous analysis.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── Data Formatters (unchanged from V1) ───────────────────────────────


def _fmt_num(val, prefix="$"):
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        if abs(val) >= 1e12:
            return f"{prefix}{val/1e12:.2f}T"
        if abs(val) >= 1e9:
            return f"{prefix}{val/1e9:.2f}B"
        if abs(val) >= 1e6:
            return f"{prefix}{val/1e6:.2f}M"
        return f"{prefix}{val:,.2f}"
    return str(val)


def _fmt_pct(val):
    if val is None:
        return "N/A"
    return f"{val*100:.2f}%" if isinstance(val, (int, float)) and abs(val) < 1 else f"{val:.2f}%" if isinstance(val, (int, float)) else str(val)


def _format_financials(financials: dict) -> str:
    lines = []
    lines.append(f"Market Cap: {_fmt_num(financials.get('market_cap'))}")
    lines.append(f"Current Price: {_fmt_num(financials.get('current_price'))}")
    lines.append(f"52W High: {_fmt_num(financials.get('52_week_high'))} | 52W Low: {_fmt_num(financials.get('52_week_low'))}")
    lines.append(f"P/E (trailing): {financials.get('pe_trailing', 'N/A')} | P/E (forward): {financials.get('pe_forward', 'N/A')}")
    lines.append(f"PEG Ratio: {financials.get('peg_ratio', 'N/A')}")
    lines.append(f"P/B: {financials.get('price_to_book', 'N/A')} | P/S: {financials.get('price_to_sales', 'N/A')}")
    lines.append(f"EV/EBITDA: {financials.get('ev_to_ebitda', 'N/A')}")
    lines.append(f"Profit Margin: {_fmt_pct(financials.get('profit_margin'))}")
    lines.append(f"Operating Margin: {_fmt_pct(financials.get('operating_margin'))}")
    lines.append(f"Gross Margin: {_fmt_pct(financials.get('gross_margin'))}")
    lines.append(f"ROE: {_fmt_pct(financials.get('roe'))} | ROA: {_fmt_pct(financials.get('roa'))}")
    lines.append(f"Revenue Growth: {_fmt_pct(financials.get('revenue_growth'))}")
    lines.append(f"Earnings Growth: {_fmt_pct(financials.get('earnings_growth'))}")
    lines.append(f"Total Revenue: {_fmt_num(financials.get('total_revenue'))}")
    lines.append(f"Net Income: {_fmt_num(financials.get('net_income'))}")
    lines.append(f"EBITDA: {_fmt_num(financials.get('ebitda'))}")
    lines.append(f"EPS (trailing): {financials.get('eps_trailing', 'N/A')} | EPS (forward): {financials.get('eps_forward', 'N/A')}")
    lines.append(f"Debt/Equity: {financials.get('debt_to_equity', 'N/A')}")
    lines.append(f"Current Ratio: {financials.get('current_ratio', 'N/A')}")
    lines.append(f"Total Cash: {_fmt_num(financials.get('total_cash'))} | Total Debt: {_fmt_num(financials.get('total_debt'))}")
    lines.append(f"Dividend Yield: {_fmt_pct(financials.get('dividend_yield'))}")
    lines.append(f"Analyst Target (mean): {_fmt_num(financials.get('target_mean'))} | Rec: {financials.get('recommendation', 'N/A')}")

    annual_rev = financials.get("annual_revenue", {})
    if annual_rev:
        lines.append("\nAnnual Revenue History:")
        for year, val in sorted(annual_rev.items(), reverse=True):
            lines.append(f"  {year}: {_fmt_num(val)}")

    annual_ni = financials.get("annual_net_income", {})
    if annual_ni:
        lines.append("\nAnnual Net Income History:")
        for year, val in sorted(annual_ni.items(), reverse=True):
            lines.append(f"  {year}: {_fmt_num(val)}")

    return "\n".join(lines)


def _format_technicals(technicals: dict) -> str:
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


def _format_competitors(competitors: list) -> str:
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
        lines.append(f"  ROE: {c.get('roe', 'N/A')} | D/E: {c.get('debt_to_equity', 'N/A')}")
        lines.append(f"  Analyst Target: ${c.get('target_mean', 'N/A')}")
    return "\n".join(lines)


def _format_news(news: list) -> str:
    if not news:
        return "No recent news available."
    lines = []
    for i, article in enumerate(news[:15], 1):
        lines.append(f"{i}. [{article.get('published', 'N/A')}] {article.get('title', 'No title')}")
        lines.append(f"   Source: {article.get('publisher', 'Unknown')}")
    return "\n".join(lines)


def _format_sector(sector_data: dict) -> str:
    lines = []
    lines.append(f"Sector: {sector_data.get('sector', 'Unknown')}")
    lines.append(f"Sector ETF: {sector_data.get('etf_ticker', 'N/A')} ({sector_data.get('etf_name', '')})")
    for label, key in [("Sector Returns", "returns"), ("S&P 500 Returns", "spy_returns")]:
        lines.append(f"\n{label}:")
        for period, ret in sector_data.get(key, {}).items():
            lines.append(f"  {period}: {ret}%" if ret is not None else f"  {period}: N/A")
    return "\n".join(lines)


# ─── LLM Call Helper ────────────────────────────────────────────────────


def _call_llm(client: OpenAI, system: str, prompt: str, max_tokens: int = 1500) -> dict:
    """Make a single LLM call and return parsed JSON."""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    try:
        result = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        result = {"raw_response": response.choices[0].message.content, "error": "parse_failed"}

    result["_tokens"] = response.usage.total_tokens
    return result


# ─── Step 1: Fundamental Analysis ──────────────────────────────────────


def analyze_fundamentals(client: OpenAI, ticker: str, company_info: dict, financials: dict) -> dict:
    """Step 1: Deep dive into financial health."""
    print(f"  [Step 1/4] Analyzing fundamentals...")

    prompt = f"""You are a fundamental equity analyst. Analyze ONLY the financial health of this company. Be very specific with numbers.

Company: {company_info.get('name', ticker)} ({ticker})
Sector: {company_info.get('sector', 'Unknown')} | Industry: {company_info.get('industry', 'Unknown')}

Description:
{company_info.get('description', 'N/A')[:800]}

Financial Metrics:
{_format_financials(financials)}

Analyze and return JSON:
{{
    "company_overview": "2-3 paragraphs: what the company does, market position, competitive moats",
    "fundamental_analysis": "3-4 paragraphs analyzing: (1) profitability — margins, ROE, ROA (2) growth — revenue/earnings trajectory with specific numbers (3) valuation — is current P/E justified? compared to sector? (4) balance sheet — debt levels, cash position, financial stability",
    "financial_health_score": "1-10, with brief justification",
    "growth_outlook": "Accelerating / Stable / Decelerating / Declining — with reasoning",
    "estimated_eps_growth_rate": "Your best estimate of annual EPS growth rate for the next 5 years, as a decimal (e.g., 0.15 for 15%)"
}}

Reference SPECIFIC numbers from the data. Don't generalize."""

    return _call_llm(client, "You are a financial analyst focused purely on fundamentals. Be precise with numbers.", prompt, max_tokens=2000)


# ─── Step 2: Technical Analysis Interpretation ─────────────────────────


def analyze_technicals_llm(client: OpenAI, ticker: str, technicals: dict, fundamental_verdict: dict) -> dict:
    """Step 2: Interpret technical setup in context of fundamentals."""
    print(f"  [Step 2/4] Interpreting technical setup...")

    prompt = f"""You are a technical analyst. Given these fundamental findings and technical indicators for {ticker}, provide your technical interpretation.

FUNDAMENTAL CONTEXT (from previous analysis):
- Financial Health Score: {fundamental_verdict.get('financial_health_score', 'N/A')}
- Growth Outlook: {fundamental_verdict.get('growth_outlook', 'N/A')}

TECHNICAL INDICATORS:
{_format_technicals(technicals)}

Return JSON:
{{
    "technical_analysis_summary": "2-3 paragraphs interpreting: (1) current trend — bullish/bearish/neutral and why (2) momentum — what RSI and MACD say about near-term direction (3) key levels — support/resistance and what happens if broken",
    "trend_alignment": "Does the technical trend AGREE or CONFLICT with the fundamental outlook? Explain.",
    "near_term_bias": "Bullish / Neutral / Bearish",
    "key_price_levels": {{
        "strong_support": <price>,
        "strong_resistance": <price>,
        "breakout_target": <price if resistance breaks>,
        "breakdown_target": <price if support breaks>
    }}
}}"""

    return _call_llm(client, "You are a technical analyst. Interpret price action and indicators precisely.", prompt, max_tokens=1200)


# ─── Step 3: Competitive & Sector Position ─────────────────────────────


def analyze_competitive_position(
    client: OpenAI, ticker: str, company_info: dict, financials: dict,
    competitors: list, sector_data: dict, news: list,
    fundamental_verdict: dict, technical_verdict: dict
) -> dict:
    """Step 3: Compare vs competitors and analyze sector dynamics."""
    print(f"  [Step 3/4] Analyzing competitive position & sector...")

    prompt = f"""You are a sector analyst. Analyze {ticker}'s position relative to its competitors and sector.

COMPANY: {company_info.get('name', ticker)} ({ticker})
Sector: {company_info.get('sector', 'Unknown')}

PREVIOUS ANALYSIS CONTEXT:
- Financial Health: {fundamental_verdict.get('financial_health_score', 'N/A')}/10
- Growth: {fundamental_verdict.get('growth_outlook', 'N/A')}
- Technical Bias: {technical_verdict.get('near_term_bias', 'N/A')}

COMPETITORS:
{_format_competitors(competitors)}

SECTOR PERFORMANCE:
{_format_sector(sector_data)}

RECENT NEWS:
{_format_news(news)}

Return JSON:
{{
    "competitor_comparison": "2-3 paragraphs: (1) How does {ticker} compare on valuation (P/E, P/S)? (2) Who has better growth? Better margins? (3) What is {ticker}'s competitive advantage or disadvantage?",
    "sector_outlook": "2-3 paragraphs: (1) Sector performance vs S&P 500 (2) Key tailwinds for this sector in next 1-5 years (3) Key headwinds or risks",
    "news_sentiment": "1-2 paragraphs: summarize recent news sentiment — positive, negative, or mixed? Any catalysts?",
    "competitive_rank": "Where does {ticker} rank among its peers? Top / Upper / Middle / Lower / Bottom — with reasoning",
    "sector_growth_multiplier": "How much is the sector likely to grow/shrink vs the overall market? Express as a multiplier (e.g., 1.2 = 20% faster than market)"
}}"""

    return _call_llm(client, "You are a sector and competitive analyst. Compare companies rigorously with data.", prompt, max_tokens=1800)


# ─── Step 4: Price Forecasting (Show Your Math) ───────────────────────


def forecast_prices(
    client: OpenAI, ticker: str, financials: dict, technicals: dict,
    fundamental_verdict: dict, technical_verdict: dict, competitive_verdict: dict
) -> dict:
    """Step 4: Calculate price targets with explicit mathematical reasoning."""
    print(f"  [Step 4/4] Calculating price targets (show your math)...")

    current_price = technicals.get('current_price', financials.get('current_price', 0))
    eps_trailing = financials.get('eps_trailing', 'N/A')
    eps_forward = financials.get('eps_forward', 'N/A')
    pe_trailing = financials.get('pe_trailing', 'N/A')
    pe_forward = financials.get('pe_forward', 'N/A')

    prompt = f"""You are a valuation specialist. Calculate price targets for {ticker} for 1, 3, and 5 years.

CURRENT DATA:
- Current Price: ${current_price}
- EPS (trailing): ${eps_trailing}
- EPS (forward): ${eps_forward}
- P/E (trailing): {pe_trailing}
- P/E (forward): {pe_forward}

INPUT FROM PREVIOUS ANALYSIS STEPS:
- Estimated EPS Growth Rate: {fundamental_verdict.get('estimated_eps_growth_rate', 'N/A')}
- Financial Health: {fundamental_verdict.get('financial_health_score', 'N/A')}/10
- Growth Outlook: {fundamental_verdict.get('growth_outlook', 'N/A')}
- Technical Bias: {technical_verdict.get('near_term_bias', 'N/A')}
- Competitive Rank: {competitive_verdict.get('competitive_rank', 'N/A')}
- Sector Growth Multiplier: {competitive_verdict.get('sector_growth_multiplier', 'N/A')}
- Key Support: ${technical_verdict.get('key_price_levels', {}).get('strong_support', 'N/A')}
- Key Resistance: ${technical_verdict.get('key_price_levels', {}).get('strong_resistance', 'N/A')}

CALCULATE STEP BY STEP for each scenario (Bull / Base / Bear):

For each timeframe (1Y, 3Y, 5Y):
1. Start with current EPS (trailing or forward, whichever is most recent)
2. Apply an annual EPS growth rate (justify the rate for each scenario)
   - Base case: use consensus/moderate growth (MUST be > 0% for a growing company)
   - Bull case: use optimistic but plausible growth
   - Bear case: use pessimistic growth (can be negative)
3. Project EPS at the end of the period: EPS × (1 + growth_rate)^years
4. Assume a forward P/E multiple (justify based on sector, growth, competitive position)
5. Calculate target price: Projected_EPS × Assumed_P/E
6. State the final target

CRITICAL RULES:
- Prices MUST differ across timeframes. 3Y targets must differ from 1Y targets, and 5Y must differ from 3Y.
- Base case must NOT equal the current price — it should reflect moderate growth.
- For the base case: 1Y_base > current_price (for growth stocks), 3Y_base > 1Y_base, 5Y_base > 3Y_base
- The math must compound: if base EPS grows 10%/year, the 3Y price should reflect 3 years of 10% compounding, not just 1 year.

Return JSON:
{{
    "price_forecast": {{
        "current_price": {current_price},
        "1_year": {{
            "bull": <calculated price>,
            "base": <calculated price>,
            "bear": <calculated price>,
            "reasoning": "1-2 sentences summarizing the key assumptions"
        }},
        "3_year": {{
            "bull": <calculated price>,
            "base": <calculated price>,
            "bear": <calculated price>,
            "reasoning": "1-2 sentences summarizing the key assumptions"
        }},
        "5_year": {{
            "bull": <calculated price>,
            "base": <calculated price>,
            "bear": <calculated price>,
            "reasoning": "1-2 sentences summarizing the key assumptions"
        }}
    }},

    "math_breakdown": {{
        "1_year": {{
            "bull": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "base": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "bear": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}}
        }},
        "3_year": {{
            "bull": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "base": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "bear": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}}
        }},
        "5_year": {{
            "bull": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "base": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}},
            "bear": {{"eps_growth": <rate>, "projected_eps": <value>, "assumed_pe": <value>, "calculated_target": <value>}}
        }}
    }},

    "risk_factors": [
        "Risk 1 with specific explanation",
        "Risk 2 with specific explanation",
        "Risk 3 with specific explanation",
        "Risk 4 with specific explanation",
        "Risk 5 with specific explanation"
    ],

    "investment_recommendation": {{
        "rating": "Strong Buy / Buy / Hold / Sell / Strong Sell",
        "summary": "2-3 sentences with your overall thesis",
        "confidence": "High / Medium / Low"
    }}
}}

IMPORTANT:
- The math must be consistent — Projected_EPS × Assumed_P/E should approximately equal the stated target price.
- DO NOT set base case = current price. The base case should reflect the expected growth trajectory.
- Each timeframe should show progressively different prices as compounding takes effect.
- Show realistic numbers grounded in the data."""

    return _call_llm(client, "You are a valuation specialist. Show your math. Every price target must be derived from EPS × P/E with justified assumptions.", prompt, max_tokens=2500)


# ─── Main Multi-Step Analysis ──────────────────────────────────────────


def analyze_with_llm(
    ticker: str,
    stock_data: dict,
    competitors: list,
    news: list,
    sector_data: dict,
    technicals: dict,
) -> dict:
    """Run the full 4-step analysis chain. Returns combined analysis dict."""
    print(f"[analyze_with_llm] Starting 4-step analysis chain for {ticker}...")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    company_info = stock_data["info"]
    financials = stock_data["financials"]

    total_tokens = 0

    # Step 1: Fundamentals
    step1 = analyze_fundamentals(client, ticker, company_info, financials)
    total_tokens += step1.pop("_tokens", 0)

    # Step 2: Technicals (builds on step 1)
    step2 = analyze_technicals_llm(client, ticker, technicals, step1)
    total_tokens += step2.pop("_tokens", 0)

    # Step 3: Competitive + Sector + News (builds on steps 1-2)
    step3 = analyze_competitive_position(
        client, ticker, company_info, financials,
        competitors, sector_data, news, step1, step2
    )
    total_tokens += step3.pop("_tokens", 0)

    # Step 4: Price Forecasting with math (builds on steps 1-3)
    step4 = forecast_prices(client, ticker, financials, technicals, step1, step2, step3)
    total_tokens += step4.pop("_tokens", 0)

    # ── Merge all results into one dict ──
    analysis = {
        # From Step 1
        "company_overview": step1.get("company_overview", ""),
        "fundamental_analysis": step1.get("fundamental_analysis", ""),
        "financial_health_score": step1.get("financial_health_score", ""),
        "growth_outlook": step1.get("growth_outlook", ""),

        # From Step 2
        "technical_analysis_summary": step2.get("technical_analysis_summary", ""),
        "trend_alignment": step2.get("trend_alignment", ""),
        "key_price_levels": step2.get("key_price_levels", {}),

        # From Step 3
        "competitor_comparison": step3.get("competitor_comparison", ""),
        "sector_outlook": step3.get("sector_outlook", ""),
        "news_sentiment": step3.get("news_sentiment", ""),
        "competitive_rank": step3.get("competitive_rank", ""),

        # From Step 4
        "price_forecast": step4.get("price_forecast", {}),
        "math_breakdown": step4.get("math_breakdown", {}),
        "risk_factors": step4.get("risk_factors", []),
        "investment_recommendation": step4.get("investment_recommendation", {}),

        # Metadata
        "_token_usage": {
            "total_tokens": total_tokens,
            "steps": 4,
        },
    }

    print(f"[analyze_with_llm] ✓ 4-step chain complete. Total tokens: {total_tokens}")
    return analysis


if __name__ == "__main__":
    print("This tool is called from the graph pipeline or run_agent.py.")
    print("It runs a 4-step analysis chain: Fundamentals → Technicals → Competitive → Forecast")
