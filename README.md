# Momentum Watcher

A real-time intraday scanner that detects momentum spikes and high-of-day breakouts on low-float, low-priced US equities. Built for active trading — clicking a symbol sends it directly to TradeZero via AutoHotkey.

## What it does

On startup it builds a filtered watchlist of equities meeting three criteria: price $1–$10, float under 10M shares, minimum daily volume of 10,000. It then opens a live WebSocket to Alpaca's SIP feed and streams trades for every ticker on that list.

Two parallel engines run against the trade stream:

**HOD tracker** — maintains a running table of each symbol's current price, % change from previous close, and cumulative volume since 4 AM ET. Sorted by % change, refreshed every 3 seconds in the browser.

**Momentum engine** — detects flash spikes in real time using three rules applied to each incoming trade: 5+ trades within 1 second with at least 3 consecutive price increases and a minimum $0.03 move, a +3% gain from the 5-minute low, and at least 1,200 shares traded in that 5-minute window. When a signal fires, it appends a new row to the momentum feed. A sound alert plays in the browser on each new event.

Clicking any symbol in the momentum or HOD table triggers two things: it loads the stock's latest news and fundamental overview (scraped from StockTitan), and it sends the ticker to TradeZero's Market Depth window via an AutoHotkey script running on Windows.

## Stack

**Backend:** Python 3, FastAPI, Uvicorn, websockets  
**Data:** Alpaca Markets (SIP WebSocket, asset list, quotes), Financial Modeling Prep (float, volume, price fallback), Polygon.io (price fallback)  
**News/Overview:** StockTitan (BeautifulSoup scraper)  
**Frontend:** HTML/JS/Tailwind CSS  
**Integration:** AutoHotkey v2 (WSL → Windows bridge via `cmd.exe`)

## Project structure

```
app/
  api/
    routes_hod.py                  # GET /hod/data
    routes_momentum.py             # GET /momentum/data
    routes_overview.py             # GET /overview/
    routes_news.py                 # GET /news/
    routes_news_overviews_stock.py # GET /news-overview/{symbol}
    routes_ahk.py                  # POST /ahk/symbol
  services/
    alpaca_ws.py          # WebSocket connection, trade + quote ingestion
    alpaca_preload.py     # Seeds volume from 4 AM before WS starts
    data_cache.py         # In-memory HOD + momentum state, daily reset
    momentum_engine.py    # Flash spike detection logic
    momentum_state.py     # Runtime deques for momentum calculations
    symbol_filter.py      # Filter pipeline entry point, cache management
    filters.py            # Price / float / volume filters with concurrency
    price_reference.py    # Previous close fetch and cache
    news_scraper.py       # StockTitan scraper (news + fundamentals)
    utils.py
  core/
    config.py
    logger.py
  templates/
    index.html            # Dashboard shell
  static/
    js/
      hod.js              # HOD table polling + sort
      momentum.js         # Momentum feed, sound alerts, symbol click
      common.js           # sendToTradeZero (AHK bridge)
      charts.js
    css/
    sounds/
      momentum.mp3
cache/
  filtered_symbols.json   # Date-stamped, reused within the same trading day
tests/
  test_api.py
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
FMP_API_KEY=your_key
POLYGON_API_KEY=your_key  # optional
```

Run:

```bash
uvicorn app.main:app --reload
```

## Filter pipeline

On first run of the day, fetches all active tradable tickers from Alpaca (NASDAQ/NYSE/AMEX), then runs three concurrent filter passes using ThreadPoolExecutor: price (Alpaca → Polygon → FMP fallbacks), float (FMP), volume (FMP). Result is written to `cache/filtered_symbols.json` with today's date. Subsequent restarts within the same day skip the pipeline and load from cache. The WebSocket subscription is sent in chunks of 200 tickers.

## Momentum detection rules

All three must pass on the same trade event:

1. 5+ trades within 1 second, with 3+ consecutive price increases and ≥ $0.03 price move within that second, average trade size ≥ 60 shares
2. Current price is ≥ +3% above the 5-minute rolling low
3. Total volume in the past 5 minutes ≥ 1,200 shares

A new row is only appended to the feed when the % gain for that symbol exceeds its previously emitted value — avoids duplicate rows for the same move.

## TradeZero integration

Clicking a symbol POSTs to `/ahk/symbol`. The server calls `cmd.exe` (via WSL) to launch an AutoHotkey v2 script that types the ticker into TradeZero's Market Depth window. Requires AutoHotkey v2 installed on Windows and the AHK script path configured in `routes_ahk.py`.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/hod/data` | HOD table as JSON array |
| GET | `/momentum/data` | Momentum events feed |
| GET | `/news-overview/{symbol}` | Latest news + fundamentals from StockTitan |
| POST | `/ahk/symbol` | Send ticker to TradeZero via AHK |