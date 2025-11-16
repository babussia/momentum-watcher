import os
import json
import requests
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from time import sleep

# ===============================
# CONFIG
# ===============================
load_dotenv()
ET = ZoneInfo("America/New_York")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

CACHE_PATH = "cache/filtered_symbols.json"
MIN_PRICE, MAX_PRICE = 1.0, 10.0
MAX_FLOAT_MIL = 10.0
MIN_VOLUME = 10000

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


# ===============================
# 1️⃣ FETCH ALL SYMBOLS
# ===============================
def get_all_symbols():
    """Get all tradable tickers from Alpaca (with fallbacks)."""
    try:
        logging.info("📊 Fetching tradable tickers from Alpaca...")
        url = "https://api.alpaca.markets/v2/assets"
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        assets = r.json()
        return [
            a["symbol"]
            for a in assets
            if a.get("status") == "active"
            and a.get("tradable")
            and a.get("exchange") in ["NASDAQ", "NYSE", "AMEX"]
        ]
    except Exception as e:
        logging.warning(f"⚠️ Alpaca asset list failed: {e}. Trying FMP fallback...")
        try:
            url = f"https://financialmodelingprep.com/api/v3/stock/list?apikey={FMP_API_KEY}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return [
                s["symbol"]
                for s in data
                if s.get("exchangeShortName") in ["NASDAQ", "NYSE", "AMEX"]
            ]
        except Exception as e2:
            logging.error(f"❌ Could not fetch symbols from any source: {e2}")
            return []


# ===============================
# 2️⃣ PRICE FILTER
# ===============================
def get_price(symbol):
    """Fetch price reliably from Alpaca → Polygon → FMP."""

    # 1️⃣ Alpaca
    try:
        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest"
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.ok:
            q = r.json().get("quote", {})
            p = q.get("ap") or q.get("bp")
            if p:
                return p
    except:
        pass

    # 2️⃣ Polygon
    if POLYGON_API_KEY:
        try:
            url = f"https://api.polygon.io/v2/last/nbbo/{symbol}?apiKey={POLYGON_API_KEY}"
            r = requests.get(url, timeout=5)
            if r.ok:
                data = r.json()
                p = data.get("results", {}).get("p")
                if p:
                    return p
        except:
            pass

    # 3️⃣ FMP (use ALWAYS if others fail)
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote-short/{symbol}?apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=5)
        if r.ok:
            d = r.json()
            if isinstance(d, list) and d:
                p = d[0].get("price")
                if p:
                    return p
    except:
        pass

    return None


def filter_by_price(symbols):
    valid = []
    with ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(get_price, s): s for s in symbols}
        for i, f in enumerate(as_completed(futures), 1):
            s = futures[f]
            price = f.result()
            if price and MIN_PRICE <= price <= MAX_PRICE:
                valid.append(s)
            if i % 300 == 0:
                logging.info(f"💵 Checked {i}/{len(symbols)} — {len(valid)} in range.")
    return valid


# ===============================
# 3️⃣ FLOAT FILTER
# ===============================
def get_float(symbol):
    """Fetch float in millions (fallbacks to None if missing)."""
    try:
        url = f"https://financialmodelingprep.com/api/v4/shares_float?symbol={symbol}&apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=4)
        if r.ok:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                val = data[0].get("floatShares")
                if val:
                    return val / 1_000_000
    except Exception:
        pass
    return None


def filter_by_float(symbols):
    valid = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(get_float, s): s for s in symbols}
        for f in as_completed(futures):
            symbol = futures[f]
            fl = f.result()

            # 🔥 Accept float <= 10M OR float missing
            if fl is None or fl <= MAX_FLOAT_MIL:
                valid.append(symbol)
    return valid



# ===============================
# 4️⃣ VOLUME FILTER
# ===============================
def get_volume(symbol):
    try:
        url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}"
        r = requests.get(url, timeout=5)
        if r.ok:
            d = r.json()
            if isinstance(d, list) and d:
                return d[0].get("volume")
    except:
        pass
    return None


def filter_by_volume(symbols):
    valid = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(get_volume, s): s for s in symbols}
        for i, f in enumerate(as_completed(futures), 1):
            s = futures[f]
            vol = f.result()
            if vol and vol >= MIN_VOLUME:
                valid.append(s)
            if i % 100 == 0:
                logging.info(f"📊 Checked {i}/{len(symbols)} volumes — {len(valid)} liquid.")
    return valid


# ===============================
# 5️⃣ MAIN ENTRY
# ===============================
def get_filtered_symbols():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
        if cache.get("date") == datetime.now(ET).date().isoformat():
            logging.info(f"💾 Loaded {len(cache['symbols'])} cached filtered symbols.")
            return cache["symbols"]

    all_symbols = get_all_symbols()
    if not all_symbols:
        return []

    priced = filter_by_price(all_symbols)
    low_float = filter_by_float(priced)
    active = filter_by_volume(low_float)

    os.makedirs("cache", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump({"date": datetime.now(ET).date().isoformat(), "symbols": active}, f)

    logging.info(
        f"💽 Cached {len(active)} final filtered tickers under ${MAX_PRICE}, "
        f"float ≤ {MAX_FLOAT_MIL}M, vol ≥ {MIN_VOLUME}."
    )
    return active
