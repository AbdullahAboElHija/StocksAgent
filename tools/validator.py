"""
validator.py — Programmatic quality validation for LLM analysis output.

Runs sanity checks on the analysis JSON and returns a list of issues.
No LLM calls — pure deterministic validation.
"""


def validate_analysis(analysis: dict, current_price: float) -> list:
    """Validate the analysis output and return a list of issues found."""
    issues = []

    if not current_price or current_price <= 0:
        return issues  # Can't validate without a valid price

    # ── 1. Completeness: All required sections present ──
    required_sections = [
        "fundamental_analysis",
        "technical_analysis_summary",
        "competitor_comparison",
        "sector_outlook",
        "news_sentiment",
        "price_forecast",
        "risk_factors",
        "investment_recommendation",
    ]
    for section in required_sections:
        val = analysis.get(section)
        if not val:
            issues.append(f"MISSING_SECTION: '{section}' is empty or missing")
        elif isinstance(val, str) and len(val.strip()) < 50:
            issues.append(f"THIN_SECTION: '{section}' is too short ({len(val.strip())} chars, expected 50+)")

    # ── 2. Forecast sanity: bear < base < bull ──
    forecast = analysis.get("price_forecast", {})
    for period in ["1_year", "3_year", "5_year"]:
        pf = forecast.get(period, {})
        bull = pf.get("bull")
        base = pf.get("base")
        bear = pf.get("bear")

        if bull is None or base is None or bear is None:
            issues.append(f"MISSING_FORECAST: {period} is missing bull/base/bear values")
            continue

        # Convert to float if string
        try:
            bull = float(bull)
            base = float(base)
            bear = float(bear)
        except (ValueError, TypeError):
            issues.append(f"INVALID_FORECAST: {period} values are not numeric (bull={bull}, base={base}, bear={bear})")
            continue

        # bear < base < bull
        if bear >= base:
            issues.append(f"ORDER_ERROR: {period} bear (${bear}) >= base (${base})")
        if base >= bull:
            issues.append(f"ORDER_ERROR: {period} base (${base}) >= bull (${bull})")

        # No negative prices
        if bear < 0:
            issues.append(f"NEGATIVE_PRICE: {period} bear is ${bear}")

        # No wildly unrealistic targets (>10x for 1Y, >20x for 5Y)
        max_multiplier = {"1_year": 5, "3_year": 10, "5_year": 20}
        if bull > current_price * max_multiplier.get(period, 10):
            issues.append(
                f"UNREALISTIC: {period} bull ${bull} is >{max_multiplier[period]}x current price ${current_price}"
            )

        # Bear shouldn't be less than 10% of current (total wipeout unlikely for S&P 500)
        if bear < current_price * 0.1:
            issues.append(
                f"UNREALISTIC: {period} bear ${bear} implies >90% drop from ${current_price}"
            )

        # Must have reasoning
        if not pf.get("reasoning"):
            issues.append(f"MISSING_REASONING: {period} forecast has no reasoning")

    # ── 2b. Flat base case detection ──
    # Base prices should increase across timeframes (compounding growth)
    try:
        base_1y = float(forecast.get("1_year", {}).get("base", 0))
        base_3y = float(forecast.get("3_year", {}).get("base", 0))
        base_5y = float(forecast.get("5_year", {}).get("base", 0))

        # Check if base equals current price (0% growth)
        if base_1y and abs(base_1y - current_price) / current_price < 0.01:
            issues.append(
                f"FLAT_BASE: 1_year base (${base_1y}) equals current price (${current_price}) — implies 0% growth"
            )

        # Check if base is flat across periods
        if base_1y and base_3y and abs(base_1y - base_3y) / max(base_1y, 1) < 0.01:
            issues.append(
                f"FLAT_BASE: 1_year base (${base_1y}) ≈ 3_year base (${base_3y}) — no compounding"
            )
        if base_3y and base_5y and abs(base_3y - base_5y) / max(base_3y, 1) < 0.01:
            issues.append(
                f"FLAT_BASE: 3_year base (${base_3y}) ≈ 5_year base (${base_5y}) — no compounding"
            )
    except (ValueError, TypeError):
        pass

    # ── 3. Math consistency (if math_breakdown provided) ──
    math = analysis.get("math_breakdown", {})
    if math:
        for period in ["1_year", "3_year", "5_year"]:
            pm = math.get(period, {})
            for scenario in ["bull", "base", "bear"]:
                sm = pm.get(scenario, {})
                eps = sm.get("projected_eps")
                pe = sm.get("assumed_pe")
                target = sm.get("calculated_target")

                if eps and pe and target:
                    try:
                        expected = float(eps) * float(pe)
                        actual = float(target)
                        # Allow 15% tolerance for rounding
                        if abs(expected - actual) / max(abs(actual), 1) > 0.15:
                            issues.append(
                                f"MATH_ERROR: {period} {scenario}: EPS({eps}) × P/E({pe}) = "
                                f"${expected:.2f}, but stated target is ${actual:.2f}"
                            )
                    except (ValueError, TypeError):
                        pass

    # ── 4. Risk factors ──
    risks = analysis.get("risk_factors", [])
    if isinstance(risks, list) and len(risks) < 3:
        issues.append(f"FEW_RISKS: Only {len(risks)} risk factors (need at least 3)")

    # ── 5. Recommendation ──
    rec = analysis.get("investment_recommendation", {})
    if not rec.get("rating"):
        issues.append("MISSING_RATING: No investment rating provided")
    if not rec.get("summary"):
        issues.append("MISSING_RATING_SUMMARY: No rating summary provided")

    return issues


def format_issues_for_reprompt(issues: list) -> str:
    """Format validation issues into a clear re-prompt for the LLM."""
    lines = ["The following issues were found in your analysis. Please fix them:\n"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. {issue}")
    lines.append("\nFix ONLY these specific issues. Keep everything else the same.")
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    test_analysis = {
        "price_forecast": {
            "1_year": {"bull": 100, "base": 90, "bear": 120, "reasoning": "test"},  # bear > base
            "3_year": {"bull": 200, "base": 150, "bear": 80},  # missing reasoning
            "5_year": {"bull": 500, "base": 300, "bear": -10},  # negative bear
        },
        "risk_factors": ["one risk"],  # too few
        "investment_recommendation": {},  # missing rating
    }
    issues = validate_analysis(test_analysis, current_price=100.0)
    print("Issues found:")
    for issue in issues:
        print(f"  ❌ {issue}")
