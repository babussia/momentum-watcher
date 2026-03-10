# app/services/data_cache.py
import logging
import os
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
import asyncio

from app.services.price_reference import get_prev_close  # fallback

MOCK_HOD_MODE = False

# =============================================
# GLOBALS
# =============================================

ET = ZoneInfo("America/New_York")

hod_data = []                 # HOD rows for UI
momentum_events = []          # 🔥 LIST of momentum events (NOT dict)

prev_closes = {}
float_cache = {}
cumulative_volume = {}
last_reset_date = None

latest_quotes = {}            # passive quote cache

CACHE_DIR = "cache"
FILTERED_TICKERS_PATH = os.path.join(CACHE_DIR, "filtered_symbols.json")
PREV_CLOSE_CACHE = os.path.join(CACHE_DIR, "prev_close_cache.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# =============================================
# CONFIG
# =============================================

MAX_HOD_SYMBOLS = 20
MAX_MOMENTUM_SYMBOLS = 10   # last 20 EVENTS (not symbols)

# =============================================
# MARKET SESSION
# =============================================

def is_market_session() -> bool:
    now_et = datetime.now(ET).time()
    return time(4, 0) <= now_et <= time(20, 0)

# =============================================
# LOADERS
# =============================================

def load_cached_filtered_tickers(path: str = FILTERED_TICKERS_PATH):
    if not os.path.exists(path):
        logging.warning(f"⚠️ Cached file not found: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("symbols", []) if isinstance(data, dict) else []
    except Exception as e:
        logging.error(f"❌ Failed to load cached tickers: {e}")
        return []


def load_float_cache():
    global float_cache

    if float_cache:
        return

    if not os.path.exists(FILTERED_TICKERS_PATH):
        logging.warning("⚠️ Float cache not found.")
        return

    try:
        with open(FILTERED_TICKERS_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)

        for entry in cache.get("symbols", []):
            sym = entry.get("symbol")
            fl = entry.get("float")
            if sym and fl is not None:
                try:
                    float_cache[sym] = float(fl)
                except Exception:
                    pass

        logging.info(f"💾 Loaded float cache for {len(float_cache)} symbols.")
    except Exception as e:
        logging.error(f"❌ Failed loading float cache: {e}")


def load_prev_close_cache():
    global prev_closes

    if prev_closes:
        return

    if not os.path.exists(PREV_CLOSE_CACHE):
        logging.warning(f"⚠️ Prev close cache file not found: {PREV_CLOSE_CACHE}")
        return

    try:
        with open(PREV_CLOSE_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for k, v in data.items():
            try:
                prev_closes[k] = float(v)
            except Exception:
                pass

        logging.info(f"💾 Loaded previous close cache ({len(prev_closes)} symbols).")
    except Exception as e:
        logging.error(f"❌ Failed to load prev_close cache: {e}")


def get_prev_close_cached(symbol: str):
    if not prev_closes:
        load_prev_close_cache()

    if symbol in prev_closes:
        return prev_closes[symbol]

    try:
        pc = get_prev_close(symbol)
        if pc is not None:
            prev_closes[symbol] = float(pc)
            return prev_closes[symbol]
    except Exception as e:
        logging.error(f"❌ Prev close fallback failed for {symbol}: {e}")

    return None

# =============================================
# DAILY RESET
# =============================================

def reset_daily_volume():
    global cumulative_volume, last_reset_date, prev_closes, hod_data, momentum_events, latest_quotes

    now_et = datetime.now(ET)
    current_day = now_et.date()

    if last_reset_date is None:
        last_reset_date = current_day
        return

    if last_reset_date != current_day and now_et.time() >= time(4, 0):
        cumulative_volume.clear()
        prev_closes.clear()
        hod_data.clear()
        momentum_events.clear()
        latest_quotes.clear()
        last_reset_date = current_day
        logging.info("🔁 Daily reset completed")

# =============================================
# HOD UPDATE
# =============================================

def update_trade(symbol: str, price, trade_volume):
    try:
        price = float(price)
        trade_volume = int(trade_volume)
    except Exception:
        return

    reset_daily_volume()
    load_float_cache()

    cumulative_volume[symbol] = cumulative_volume.get(symbol, 0) + trade_volume
    total_volume = cumulative_volume[symbol]

    if total_volume < 10_000:
        return

    prev_close = prev_closes.get(symbol)
    if prev_close is None:
        prev_close = get_prev_close_cached(symbol)
        if not prev_close or prev_close <= 0:
            prev_close = price

    chg = ((price - prev_close) / prev_close) * 100 if prev_close else 0.0

    now = datetime.now(ET)
    symbol_float = float_cache.get(symbol, 0.0)

    payload = {
        "symbol": symbol,
        "price": round(price, 2),
        "chg": round(chg, 2),
        "float": symbol_float,
        "spread": 0.0,
        "volume": total_volume,
        "time": now.strftime("%H:%M:%S"),
    }

    existing = next((s for s in hod_data if s["symbol"] == symbol), None)
    if existing:
        existing.update(payload)
    else:
        hod_data.append(payload)

# =============================================
# QUOTE CACHE (PASSIVE)
# =============================================

def update_quote(symbol: str, bid: float, ask: float, ts: datetime):
    try:
        bid = float(bid)
        ask = float(ask)
    except Exception:
        return

    if bid <= 0 or ask <= 0:
        return

    latest_quotes[symbol] = {
        "bid": bid,
        "ask": ask,
        "spread": round(ask - bid, 4),
        "ts": ts.timestamp(),
    }

# =============================================
# GETTERS (API)
# =============================================

def get_hod_data():
    if MOCK_HOD_MODE:
        return MOCK_HOD_DATA

    return sorted(
        hod_data,
        key=lambda x: x.get("chg", 0),
        reverse=True
    )[:MAX_HOD_SYMBOLS]


def get_momentum_data():
    """
    Return last N momentum EVENTS (not symbols)
    """
    return momentum_events[-MAX_MOMENTUM_SYMBOLS:]

# =============================================
# RESET LOOP
# =============================================

async def reset_loop():
    while True:
        now_et = datetime.now(ET)
        if now_et.hour == 4 and now_et.minute == 0 and now_et.second == 0:
            reset_daily_volume()
            await asyncio.sleep(1)
        await asyncio.sleep(0.5)

# =============================================
# MOCK DATA
# =============================================

MOCK_HOD_DATA = [
    {
        "symbol": "AAPL",
        "price": 195.42,
        "chg": 2.31,
        "float": 15.8,
        "spread": 0.01,
        "volume": 74200000,
        "time": "10:14:23"
    }
]