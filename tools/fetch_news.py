"""
fetch_news.py — Fetches recent news for a given ticker.

Usage:
    from tools.fetch_news import fetch_news
    news = fetch_news("AAPL")

Returns a list of dicts with keys: title, publisher, link, published
"""

import sys
import yfinance as yf
from datetime import datetime


def fetch_news(ticker: str) -> list:
    """Fetch recent news articles for a given ticker."""
    print(f"[fetch_news] Fetching news for {ticker}...")

    stock = yf.Ticker(ticker)
    raw_news = stock.news or []

    articles = []
    for item in raw_news[:20]:  # Cap at 20 articles
        # yfinance news format can vary by version
        if isinstance(item, dict):
            # Extract from content structure if present
            content = item.get("content", item)
            if isinstance(content, dict):
                title = content.get("title", item.get("title", "No title"))
                publisher = content.get("provider", {})
                if isinstance(publisher, dict):
                    publisher = publisher.get("displayName", "Unknown")
                elif isinstance(publisher, str):
                    pass
                else:
                    publisher = item.get("publisher", "Unknown")

                link = content.get("canonicalUrl", {})
                if isinstance(link, dict):
                    link = link.get("url", item.get("link", ""))
                elif not isinstance(link, str):
                    link = item.get("link", "")

                pub_date = content.get("pubDate", item.get("providerPublishTime", ""))
            else:
                title = item.get("title", "No title")
                publisher = item.get("publisher", "Unknown")
                link = item.get("link", "")
                pub_date = item.get("providerPublishTime", "")

            # Convert timestamp to readable date
            if isinstance(pub_date, (int, float)):
                try:
                    pub_date = datetime.fromtimestamp(pub_date).strftime("%Y-%m-%d %H:%M")
                except (OSError, ValueError):
                    pub_date = str(pub_date)
            elif isinstance(pub_date, str) and pub_date:
                # Try to clean up ISO format dates
                try:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    pub_date = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass

            articles.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "published": pub_date,
            })

    print(f"[fetch_news] Done. Found {len(articles)} articles.")
    return articles


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_news.py <TICKER>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    news = fetch_news(ticker)

    print(f"\n{'='*60}")
    print(f"  Recent News for {ticker}")
    print(f"{'='*60}")
    for i, article in enumerate(news, 1):
        print(f"  {i:2d}. [{article['published']}] {article['title']}")
        print(f"      Source: {article['publisher']}")
