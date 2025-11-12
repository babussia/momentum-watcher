# app/services/data_cache.py
import logging
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


# =============================================
# DAILY RESET
# =============================================
def reset_daily_volume():
    """Reset cumulative volume once per new day at 4:00 AM ET."""
    global cumulative_volume, last_reset_date

    now_et = datetime.now(ET)
    current_day = now_et.date()

    # Initialize the first run
    if last_reset_date is None:
        last_reset_date = current_day
        logging.info(f"🕓 ET time now: {now_et.strftime('%Y-%m-%d %H:%M:%S')} | Initial load.")
        return  # ✅ skip clearing preload on startup

    # Only reset once when a *new day* starts AND after 4 AM ET
    if last_reset_date != current_day and now_et.time() >= time(4, 0):
        cumulative_volume.clear()
        last_reset_date = current_day
        logging.info(f"🔁 Daily volume reset at {now_et.strftime('%Y-%m-%d %H:%M:%S ET')}")



# =============================================
# UPDATE TRADE
# =============================================
def update_trade(symbol: str, price: float, trade_volume: int):
    """Update or insert symbol HOD data, tracking cumulative volume since 4 AM."""
    now = datetime.now(ET)
    reset_daily_volume()

    # ✅ Merge with preloaded cumulative volume (if exists)
    if symbol in cumulative_volume:
        cumulative_volume[symbol] += trade_volume
    else:
        cumulative_volume[symbol] = trade_volume

    total_volume = cumulative_volume[symbol]

    # ✅ Get previous close (cached or fetched)
    prev_close = prev_closes.get(symbol)
    if prev_close is None:
        prev_close = get_previous_close(symbol)
        if prev_close:
            prev_closes[symbol] = prev_close
        else:
            prev_close = price  # fallback

    # ✅ Calculate % change
    chg = ((price - prev_close) / prev_close) * 100 if prev_close else 0.0

    # ✅ Update or insert record
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
# GETTER
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