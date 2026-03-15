# Analyze Stock — Workflow SOP

## Objective
Given a stock ticker (e.g., `AAPL`), run a full analysis and produce a professional PDF report with forecasts.

## Required Inputs
- **Ticker**: A valid stock ticker traded on a major US exchange (NYSE / NASDAQ)
- **OPENAI_API_KEY**: Must be set in `.env`

## Pipeline

### Step 1: Fetch Stock Data
- **Tool**: `tools/fetch_stock_data.py`
- Pulls 5 years of daily price history (OHLCV) via `yfinance`
- Extracts 40+ financial metrics (valuation, profitability, growth, health)
- Gets company info (sector, industry, description)
- **If it fails**: Ticker is likely invalid. Verify and retry.

### Step 2: Identify Competitors
- **Tool**: `tools/fetch_competitors.py`
- Sends company info to GPT-4o → returns 5 competitor tickers
- Fetches financial data for each competitor via `yfinance`
- **If it fails**: Non-critical. Continue with empty competitor list.

### Step 3: Fetch News
- **Tool**: `tools/fetch_news.py`
- Uses `yfinance` built-in news feed
- Returns up to 20 recent articles (title, source, date)
- **If it fails**: Non-critical. Continue with empty news list.

### Step 4: Sector Analysis
- **Tool**: `tools/fetch_sector_data.py`
- Maps sector to SPDR ETF (e.g., Technology → XLK)
- Calculates 1M, 3M, 6M, 1Y, 3Y, 5Y returns
- Compares against S&P 500 (SPY)
- **If it fails**: Non-critical. Continue with basic sector info.

### Step 5: Technical Analysis
- **Tool**: `tools/analyze_technical.py`
- Calculates: SMA 50/200, EMA 20, RSI (14), MACD (12,26,9)
- Finds support/resistance levels
- Generates chart PNG → saved to `.tmp/{TICKER}_chart.png`
- **If it fails**: Non-critical. Continue without chart.

### Step 6: LLM Deep Analysis
- **Tool**: `tools/analyze_with_llm.py`
- Sends ALL collected data to GPT-4o in a structured prompt
- Returns JSON with:
  - Company overview, fundamental analysis, technical summary
  - Competitor comparison, sector outlook, news sentiment
  - Price forecasts (1Y/3Y/5Y × Bull/Base/Bear)
  - Risk factors, investment recommendation
- **Cost**: ~$0.02–0.05 per analysis
- **If it fails**: Critical. Check API key. Retry once.

### Step 7: Generate PDF
- **Tool**: `tools/generate_pdf.py`
- Builds multi-page A4 report using `reportlab`
- Embeds chart, tables, all analysis sections
- Saves to project root: `{TICKER}_Report_{date}.pdf`

## How to Run
```bash
# Single ticker
python tools/run_agent.py AAPL

# Multiple tickers
python tools/run_agent.py AAPL MSFT GOOGL
```

## Expected Output
- `{TICKER}_Report_{YYYY-MM-DD}.pdf` in project root
- Chart PNG in `.tmp/` (disposable)

## Edge Cases & Notes
- **Invalid ticker**: Script will fail at Step 1 with a yfinance error
- **No API key**: Script exits with clear error message at Step 6
- **Rate limits**: yfinance is free and generally unlimited; OpenAI has per-minute token limits
- **Non-US stocks**: May work but competitor identification may be less accurate
- **Cost tracking**: Token usage is logged in the terminal and in the PDF footer
