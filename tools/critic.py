"""
critic.py — LLM-powered critic that reviews the analysis like a senior portfolio manager.

Usage:
    from tools.critic import critique_analysis
    critique = critique_analysis(ticker, analysis)

Returns a dict with critique text and specific issues.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def critique_analysis(ticker: str, analysis: dict, current_price: float) -> dict:
    """Have a senior portfolio manager critique the analysis."""
    print(f"[critic] Reviewing analysis for {ticker}...")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build a summary of the analysis for the critic
    forecast = analysis.get("price_forecast", {})
    rec = analysis.get("investment_recommendation", {})

    analysis_summary = f"""
COMPANY: {ticker}
CURRENT PRICE: ${current_price}

FUNDAMENTAL ANALYSIS:
{analysis.get('fundamental_analysis', 'N/A')[:1500]}

TECHNICAL ANALYSIS:
{analysis.get('technical_analysis_summary', 'N/A')[:800]}

COMPETITOR COMPARISON:
{analysis.get('competitor_comparison', 'N/A')[:800]}

SECTOR OUTLOOK:
{analysis.get('sector_outlook', 'N/A')[:600]}

PRICE FORECASTS:
1-Year: Bull=${forecast.get('1_year', {}).get('bull', '?')} / Base=${forecast.get('1_year', {}).get('base', '?')} / Bear=${forecast.get('1_year', {}).get('bear', '?')}
3-Year: Bull=${forecast.get('3_year', {}).get('bull', '?')} / Base=${forecast.get('3_year', {}).get('base', '?')} / Bear=${forecast.get('3_year', {}).get('bear', '?')}
5-Year: Bull=${forecast.get('5_year', {}).get('bull', '?')} / Base=${forecast.get('5_year', {}).get('base', '?')} / Bear=${forecast.get('5_year', {}).get('bear', '?')}

MATH BREAKDOWN:
{json.dumps(analysis.get('math_breakdown', {}), indent=2)[:1000]}

RATING: {rec.get('rating', 'N/A')} (Confidence: {rec.get('confidence', 'N/A')})
SUMMARY: {rec.get('summary', 'N/A')}

RISK FACTORS:
{json.dumps(analysis.get('risk_factors', []), indent=2)[:600]}
"""

    prompt = f"""You are a senior portfolio manager with 25 years of experience. A junior analyst has produced the following stock analysis report for {ticker}. Your job is to critically review it.

{analysis_summary}

Provide your critique in the following JSON format:

{{
    "overall_assessment": "1 paragraph — Is this analysis sound? Would you trust it for investment decisions?",

    "strengths": [
        "Specific strength 1",
        "Specific strength 2"
    ],

    "weaknesses": [
        "Specific weakness or gap 1",
        "Specific weakness or gap 2",
        "Specific weakness or gap 3"
    ],

    "forecast_review": "1-2 paragraphs — Are the price targets justified by the math and data? Are the assumptions reasonable? Where might the analyst be too optimistic or pessimistic?",

    "missed_risks": [
        "Risk the analyst didn't consider 1",
        "Risk the analyst didn't consider 2"
    ],

    "adjusted_confidence": "High / Medium / Low — Your confidence in this analysis after review",

    "key_question": "The single most important question an investor should ask before acting on this analysis"
}}

Be constructive but honest. Challenge assumptions. Don't just agree with everything.
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        messages=[
            {
                "role": "system",
                "content": "You are a skeptical, experienced portfolio manager. Find holes in the analysis. Be specific."
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.5,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    try:
        critique = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        critique = {
            "overall_assessment": response.choices[0].message.content,
            "error": "Failed to parse structured critique"
        }

    usage = response.usage
    critique["_token_usage"] = {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }

    print(f"[critic] Done. Confidence: {critique.get('adjusted_confidence', 'N/A')}. Used {usage.total_tokens} tokens.")
    return critique


if __name__ == "__main__":
    print("This tool is meant to be called from the graph pipeline.")
