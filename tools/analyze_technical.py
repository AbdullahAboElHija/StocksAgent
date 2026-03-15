"""
analyze_technical.py — Calculates technical indicators and generates price chart.

Usage:
    from tools.analyze_technical import analyze_technical
    technicals = analyze_technical(ticker, history_df, tmp_dir)

Returns a dict with technical indicators and path to the saved chart PNG.
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter


def _calculate_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def _calculate_ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def _calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _calculate_ema(series, fast)
    ema_slow = _calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _find_support_resistance(history: pd.DataFrame, window: int = 20) -> dict:
    """Find approximate support and resistance levels from recent price action."""
    recent = history.tail(window * 5)  # Use last ~100 trading days
    highs = recent["High"]
    lows = recent["Low"]

    # Simple method: use rolling min/max clusters
    resistance = float(highs.rolling(window).max().dropna().median())
    support = float(lows.rolling(window).min().dropna().median())

    return {"support": round(support, 2), "resistance": round(resistance, 2)}


def analyze_technical(ticker: str, history: pd.DataFrame, tmp_dir: str) -> dict:
    """Calculate technical indicators and generate chart."""
    print(f"[analyze_technical] Running technical analysis for {ticker}...")

    close = history["Close"]
    high = history["High"]
    low = history["Low"]

    # --- Calculate Indicators ---
    sma_50 = _calculate_sma(close, 50)
    sma_200 = _calculate_sma(close, 200)
    ema_20 = _calculate_ema(close, 20)
    rsi = _calculate_rsi(close, 14)
    macd_line, signal_line, macd_hist = _calculate_macd(close)
    support_resistance = _find_support_resistance(history)

    current_price = float(close.iloc[-1])
    current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    current_macd = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None
    current_signal = float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None
    current_sma50 = float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None
    current_sma200 = float(sma_200.iloc[-1]) if not pd.isna(sma_200.iloc[-1]) else None
    current_ema20 = float(ema_20.iloc[-1]) if not pd.isna(ema_20.iloc[-1]) else None

    # --- Trend determination ---
    trend = "Neutral"
    if current_sma50 and current_sma200:
        if current_price > current_sma50 > current_sma200:
            trend = "Strong Bullish"
        elif current_price > current_sma50:
            trend = "Bullish"
        elif current_price < current_sma50 < current_sma200:
            trend = "Strong Bearish"
        elif current_price < current_sma50:
            trend = "Bearish"

    # RSI interpretation
    rsi_signal = "Neutral"
    if current_rsi:
        if current_rsi > 70:
            rsi_signal = "Overbought"
        elif current_rsi < 30:
            rsi_signal = "Oversold"

    # MACD interpretation
    macd_signal = "Neutral"
    if current_macd is not None and current_signal is not None:
        if current_macd > current_signal:
            macd_signal = "Bullish"
        else:
            macd_signal = "Bearish"

    # --- Generate Chart ---
    chart_path = os.path.join(tmp_dir, f"{ticker}_chart.png")
    _generate_chart(
        ticker, history, sma_50, sma_200, ema_20, rsi,
        macd_line, signal_line, macd_hist, chart_path
    )

    indicators = {
        "current_price": round(current_price, 2),
        "sma_50": round(current_sma50, 2) if current_sma50 else None,
        "sma_200": round(current_sma200, 2) if current_sma200 else None,
        "ema_20": round(current_ema20, 2) if current_ema20 else None,
        "rsi_14": round(current_rsi, 2) if current_rsi else None,
        "rsi_signal": rsi_signal,
        "macd": round(current_macd, 4) if current_macd else None,
        "macd_signal_line": round(current_signal, 4) if current_signal else None,
        "macd_interpretation": macd_signal,
        "trend": trend,
        "support": support_resistance["support"],
        "resistance": support_resistance["resistance"],
        "52_week_high": round(float(high.tail(252).max()), 2),
        "52_week_low": round(float(low.tail(252).min()), 2),
        "chart_path": chart_path,
    }

    print(f"[analyze_technical] Done. Trend: {trend} | RSI: {rsi_signal} | MACD: {macd_signal}")
    return indicators


def _generate_chart(ticker, history, sma_50, sma_200, ema_20, rsi,
                    macd_line, signal_line, macd_hist, output_path):
    """Generate a professional multi-panel price chart."""
    # Use last 1 year for cleaner chart
    lookback = min(252, len(history))
    hist = history.tail(lookback)
    idx = hist.index

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[3, 1, 1],
                              gridspec_kw={"hspace": 0.3})

    fig.patch.set_facecolor("#1a1a2e")

    # --- Panel 1: Price + Moving Averages ---
    ax1 = axes[0]
    ax1.set_facecolor("#16213e")
    ax1.plot(idx, hist["Close"], color="#00d4ff", linewidth=1.5, label="Price", zorder=3)
    ax1.plot(idx, sma_50.loc[idx], color="#ff6b6b", linewidth=1, alpha=0.8, label="SMA 50")
    ax1.plot(idx, sma_200.loc[idx], color="#ffd93d", linewidth=1, alpha=0.8, label="SMA 200")
    ax1.plot(idx, ema_20.loc[idx], color="#6bcb77", linewidth=0.8, alpha=0.6, label="EMA 20")
    ax1.fill_between(idx, hist["Low"], hist["High"], alpha=0.1, color="#00d4ff")
    ax1.set_title(f"{ticker} — Technical Analysis", color="white", fontsize=14, fontweight="bold", pad=10)
    ax1.legend(loc="upper left", fontsize=8, facecolor="#16213e", edgecolor="gray", labelcolor="white")
    ax1.tick_params(colors="gray")
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax1.grid(color="gray", alpha=0.2)

    # --- Panel 2: RSI ---
    ax2 = axes[1]
    ax2.set_facecolor("#16213e")
    rsi_vals = rsi.loc[idx]
    ax2.plot(idx, rsi_vals, color="#ff6b6b", linewidth=1)
    ax2.axhline(70, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
    ax2.axhline(30, color="green", linestyle="--", alpha=0.5, linewidth=0.8)
    ax2.fill_between(idx, 70, rsi_vals, where=rsi_vals > 70, alpha=0.3, color="red")
    ax2.fill_between(idx, 30, rsi_vals, where=rsi_vals < 30, alpha=0.3, color="green")
    ax2.set_title("RSI (14)", color="white", fontsize=10, pad=5)
    ax2.set_ylim(0, 100)
    ax2.tick_params(colors="gray")
    ax2.grid(color="gray", alpha=0.2)

    # --- Panel 3: MACD ---
    ax3 = axes[2]
    ax3.set_facecolor("#16213e")
    macd_vals = macd_line.loc[idx]
    signal_vals = signal_line.loc[idx]
    hist_vals = macd_hist.loc[idx]
    ax3.plot(idx, macd_vals, color="#00d4ff", linewidth=1, label="MACD")
    ax3.plot(idx, signal_vals, color="#ff6b6b", linewidth=1, label="Signal")
    colors = ["#6bcb77" if v >= 0 else "#ff6b6b" for v in hist_vals]
    ax3.bar(idx, hist_vals, color=colors, alpha=0.5, width=1.5)
    ax3.axhline(0, color="gray", linewidth=0.5)
    ax3.set_title("MACD (12, 26, 9)", color="white", fontsize=10, pad=5)
    ax3.legend(loc="upper left", fontsize=8, facecolor="#16213e", edgecolor="gray", labelcolor="white")
    ax3.tick_params(colors="gray")
    ax3.grid(color="gray", alpha=0.2)

    # Format x-axis dates
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        for spine in ax.spines.values():
            spine.set_color("gray")
            spine.set_linewidth(0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"[analyze_technical] Chart saved to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_technical.py <TICKER>")
        sys.exit(1)

    from tools.fetch_stock_data import fetch_stock_data

    ticker = sys.argv[1].upper()
    data = fetch_stock_data(ticker)

    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    result = analyze_technical(ticker, data["history"], tmp_dir)

    print(f"\n{'='*60}")
    print(f"  Technical Indicators for {ticker}")
    print(f"{'='*60}")
    for key, val in result.items():
        if key != "chart_path":
            print(f"  {key:>20s}: {val}")
    print(f"  {'chart_path':>20s}: {result['chart_path']}")
