# app/services/data_cache.py
import logging
import os
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
from app.services.price_reference import get_previous_close
import asyncio

# =============================================
# GLOBALS
# =============================================
ET = ZoneInfo("America/New_York")

hod_data = []                # Stores symbol data for frontend
prev_closes = {}             # Cache of previous closes
cumulative_volume = {}       # Track total volume per symbol
last_reset_date = None

CACHE_DIR = "cache"
FILTERED_TICKERS_PATH = os.path.join(CACHE_DIR, "filtered_symbols.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


# =============================================
# MARKET WINDOW / CACHE HELPERS
# =============================================
def is_market_session() -> bool:
    """
    Return True if current ET time is within 4:00–20:00 (8 PM) ET.
    Used by preload to decide whether to preload ALL filtered tickers.
    """
    now_et = datetime.now(ET).time()
    return time(4, 0) <= now_et <= time(20, 0)


def load_cached_filtered_tickers(path: str = FILTERED_TICKERS_PATH) -> list[str]:
    """
    Load cached filtered tickers from file created by symbol_filter.py.
    Supports formats: {"symbols": [...]}, {"tickers": [...]}, or plain list.
    """
    import json, os, logging

    if not os.path.exists(path):
        logging.warning(f"⚠️ Cached file not found: {path}")
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            if "symbols" in data:
                return data["symbols"]
            elif "tickers" in data:
                return data["tickers"]
        elif isinstance(data, list):
            return data

        logging.warning(f"⚠️ Unrecognized format in {path}")
        return []
    except Exception as e:
        logging.error(f"❌ Failed to load cached tickers: {e}")
        return []



def save_cached_filtered_tickers(tickers: list[str], path: str = FILTERED_TICKERS_PATH) -> None:
    """
    Optional utility if you want to persist filtered tickers for reuse.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tickers, f)
        logging.info(f"💾 Saved {len(tickers)} filtered tickers to {path}")
    except Exception as e:
        logging.error(f"❌ Failed to save filtered tickers: {e}")


# =============================================
# DAILY RESET
# =============================================
def reset_daily_volume():
    global cumulative_volume, last_reset_date, prev_closes

    now_et = datetime.now(ET)
    current_day = now_et.date()

    if last_reset_date is None:
        last_reset_date = current_day
        logging.info(f"🕓 ET time now: {now_et.strftime('%Y-%m-%d %H:%M:%S')} | Initial load.")
        return

    if last_reset_date != current_day and now_et.time() >= time(4, 0):
        cumulative_volume.clear()
        prev_closes.clear()  # ✅ added line
        last_reset_date = current_day
        logging.info(f"🔁 Daily reset at {now_et.strftime('%Y-%m-%d %H:%M:%S ET')}")



# =============================================
# UPDATE TRADE
# =============================================
def update_trade(symbol: str, price: float, trade_volume: int):
    """
    Update or insert symbol HOD data, tracking cumulative volume since 4 AM.
    Preloaded volume (from the preload step) is already seeded in cumulative_volume.
    """
    now = datetime.now(ET)
    reset_daily_volume()

    # Merge live trade volume with preloaded volume baseline
    cumulative_volume[symbol] = cumulative_volume.get(symbol, 0) + trade_volume
    total_volume = cumulative_volume[symbol]

    # Get previous close (cached or fetched)
    prev_close = prev_closes.get(symbol)
    if prev_close is None:
        prev_close = get_previous_close(symbol)
        if prev_close:
            prev_closes[symbol] = prev_close
        else:
            prev_close = price  # fallback if API fails

    chg = ((price - prev_close) / prev_close) * 100 if prev_close else 0.0

    existing = next((s for s in hod_data if s["symbol"] == symbol), None)
    if existing:
        existing.update({
            "price": round(price, 2),
            "chg": round(chg, 2),
            "volume": total_volume,
            "time": now.strftime("%H:%M:%S"),
        })
    else:
        hod_data.append({
            "symbol": symbol,
            "price": round(price, 2),
            "chg": round(chg, 2),
            "float": 0.0,
            "spread": 0.0,
            "volume": total_volume,
            "time": now.strftime("%H:%M:%S"),
        })

    logging.info(f"🔥 {symbol} {price:.2f} ({chg:+.2f}%) | Vol: {total_volume:,}")


# =============================================
# GETTERS
# =============================================
def get_hod_data():
    """Return cached HOD data."""
    return hod_data


async def reset_loop():
    """Auto-reset cumulative volume every day at exactly 4:00:00 ET."""
    while True:
        now_et = datetime.now(ET)
        if now_et.hour == 4 and now_et.minute == 0 and now_et.second == 0:
            reset_daily_volume()
            logging.info("⏰ Auto daily volume reset triggered at 4:00:00 ET")
            await asyncio.sleep(1)
        await asyncio.sleep(0.5)
