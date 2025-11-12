import os
import json
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# ===============================
# CONFIG
# ===============================
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

CACHE_FLOATS = {}
ET = ZoneInfo("America/New_York")
PRICE_FILTER_CACHE = "cache/filtered_symbols.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

MIN_PRICE = 0.1
MAX_PRICE = 10.0
MAX_FLOAT_MILLIONS = 10.0


# =======================
# 1️⃣ FETCH ALL SYMBOLS
# =======================
def get_all_symbols():
    """Get all active tradable symbols from Alpaca."""
    logging.info("📊 Fetching all tradable tickers from Alpaca...")
    url = "https://api.alpaca.markets/v2/assets"
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    assets = r.json()
    return [
        a["symbol"]
        for a in assets
        if a.get("status") == "active"
        and a.get("tradable")
        and a.get("exchange") in ["NYSE", "NASDAQ", "AMEX"]
    ]


# =======================
# 2️⃣ PRICE FILTER (FAST)
# =======================
def get_price(symbol):
    """Fetch last trade price for a symbol (returns None if fails)."""
    try:
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        price = data.get("quote", {}).get("ap") or data.get("quote", {}).get("bp")
        return price
    except Exception:
        return None


def filter_by_price(symbols):
    """Return only symbols within target price range."""
    valid = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(get_price, s): s for s in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            price = future.result()
            if price and MIN_PRICE <= price <= MAX_PRICE:
                valid.append(symbol)
            if i % 500 == 0:
                logging.info(
                    f"💵 Checked {i}/{len(symbols)} symbols — {len(valid)} in range so far."
                )
    logging.info(f"✅ Price filter done — {len(valid)} symbols under ${MAX_PRICE}.")
    return valid


# =======================
# 3️⃣ FLOAT FILTER (CACHED)
# =======================
def get_float(symbol):
    """Fetch float (in millions) from FMP v4/shares_float endpoint, cached."""
    if symbol in CACHE_FLOATS:
        return CACHE_FLOATS[symbol]

    try:
        url = f"https://financialmodelingprep.com/api/v4/shares_float?symbol={symbol}&apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                float_val = item.get("floatShares") or item.get("freeFloat")
                if float_val:
                    float_mil = float_val / 1_000_000  # convert to millions
                    CACHE_FLOATS[symbol] = float_mil
                    return float_mil
    except Exception as e:
        logging.debug(f"⚠️ Error getting float for {symbol}: {e}")
        pass

    return None


def filter_by_float(symbols):
    """Filter by float size (< MAX_FLOAT_MILLIONS)."""
    valid = []
    with ThreadPoolExecutor(max_workers=10) as executor:  # respect FMP rate limits
        futures = {executor.submit(get_float, s): s for s in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            f = future.result()
            if f and f <= MAX_FLOAT_MILLIONS:
                valid.append(symbol)
            if i % 50 == 0:
                logging.info(
                    f"🧮 Checked {i}/{len(symbols)} floats — {len(valid)} passed."
                )
            sleep(0.2)  # ~5 requests/sec = 300/min
    logging.info(f"✅ Float filter done — {len(valid)} low-float stocks found.")
    return valid


# =======================
# 4️⃣ MAIN ENTRY
# =======================
def get_filtered_symbols():
    """Fetch all tradable tickers, then filter by price and float."""

    # === Load same-day cache (if exists)
    if os.path.exists(PRICE_FILTER_CACHE):
        try:
            with open(PRICE_FILTER_CACHE, "r") as f:
                cache = json.load(f)
            cache_date = cache.get("date")
            today = datetime.now(ET).date().isoformat()
            if cache_date == today:
                cached_symbols = cache.get("symbols", [])
                logging.info(
                    f"💾 Loaded {len(cached_symbols)} cached float-filtered symbols from today."
                )
                return cached_symbols
        except Exception:
            pass

    # === Step 1: Get all tradable tickers
    all_symbols = get_all_symbols()

    # === Step 2: Filter by price
    under_10 = filter_by_price(all_symbols)

    # === Step 3: Filter by float
    low_float = filter_by_float(under_10)

    # === Cache today's FINAL filtered list (price + float)
    os.makedirs("cache", exist_ok=True)
    with open(PRICE_FILTER_CACHE, "w") as f:
        json.dump(
            {"date": datetime.now(ET).date().isoformat(), "symbols": low_float}, f
        )
    logging.info(f"💽 Cached {len(low_float)} final filtered tickers for today.")

    logging.info(
        f"🏁 Final filtered list: {len(low_float)} symbols under ${MAX_PRICE} and under {MAX_FLOAT_MILLIONS}M float."
    )
    return low_float
