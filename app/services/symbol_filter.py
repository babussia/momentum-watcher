import os
import json
import logging
import requests
from math import ceil
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# ======================================================
# ENV / KEYS
# ======================================================

load_dotenv()

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
FMP_KEY = os.getenv("FMP_API_KEY")

ALP_HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

ET = ZoneInfo("America/New_York")

# ======================================================
# CACHE FILES
# ======================================================

CACHE_RAW = "cache/alpaca_tradable.json"
CACHE_PREV = "cache/prevclose_stage.json"
CACHE_PRICE = "cache/price_stage.json"
CACHE_FINAL = "cache/filtered_symbols.json"
PREV_CLOSE_CACHE = "cache/prev_close_cache.json"

# ======================================================
# FILTER RULES
# ======================================================

MIN_PRICE = 0.30
MAX_PRICE = 10.00
MAX_FLOAT = 10.0  # million

# ======================================================
# LOGGING
# ======================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# ======================================================
# HELPERS
# ======================================================

def _ensure_cache_dir():
    os.makedirs("cache", exist_ok=True)

def _today_et() -> str:
    return datetime.now(ET).date().isoformat()

def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _write_json(path: str, data):
    _ensure_cache_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _stage_is_today(path: str) -> bool:
    obj = _read_json(path)
    if not isinstance(obj, dict):
        return False
    return obj.get("date") == _today_et()

def _load_stage_symbols(path: str):
    obj = _read_json(path)
    if isinstance(obj, dict) and isinstance(obj.get("symbols"), list):
        return obj["symbols"]
    return None

def _utc_date_range(days_back: int):
    today_utc = datetime.now(timezone.utc).date()
    start_utc = today_utc - timedelta(days=days_back)
    return start_utc.isoformat(), today_utc.isoformat()

# ======================================================
# STEP 1 - GET TRADABLE TICKERS
# ======================================================

def get_tradable():
    obj = _read_json(CACHE_RAW)
    if isinstance(obj, dict) and obj.get("date") == _today_et():
        logging.info(f"💾 Using cached TRADABLE: {len(obj['symbols'])}")
        return obj["symbols"]

    logging.info("📡 Fetching Alpaca tradable tickers...")
    r = requests.get(
        "https://api.alpaca.markets/v2/assets",
        headers=ALP_HEADERS,
        timeout=15,
    )
    r.raise_for_status()

    tradable = [
        d["symbol"]
        for d in r.json()
        if d.get("tradable")
        and d.get("status") == "active"
        and d.get("exchange") in ["NYSE", "NASDAQ", "AMEX"]
    ]

    _write_json(CACHE_RAW, {"date": _today_et(), "symbols": tradable})
    logging.info(f"✅ Tradable symbols: {len(tradable)}")
    return tradable

# ======================================================
# STEP 2 - LAST CLOSE (BULK)
# ======================================================

def get_last_close_bulk(symbols, days_back=10):
    if not symbols:
        return {}

    start, end = _utc_date_range(days_back)
    sym_str = ",".join(symbols)

    url = (
        "https://data.alpaca.markets/v2/stocks/bars"
        f"?symbols={sym_str}"
        "&timeframe=1Day"
        f"&start={start}"
        f"&end={end}"
        "&limit=10000"
        "&adjustment=raw"
        "&feed=sip"
        "&sort=asc"
    )

    r = requests.get(url, headers=ALP_HEADERS, timeout=30)
    if not r.ok:
        return {}

    data = r.json().get("bars", {})
    out = {}

    for sym in symbols:
        bars = data.get(sym)
        if not bars:
            continue
        last = bars[-1]
        if last.get("c") is not None:
            out[sym] = {
                "close": last["c"],
                "date": last["t"][:10],
            }

    return out

# ======================================================
# STEP 3 - FLOAT (THREAD-SAFE)
# ======================================================

def fmp_float_safe(symbol: str):
    if not FMP_KEY:
        return None

    url = (
        "https://financialmodelingprep.com/api/v4/shares_float"
        f"?symbol={symbol}&apikey={FMP_KEY}"
    )

    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None

        data = r.json()
        if isinstance(data, list) and data:
            fs = data[0].get("floatShares")
            if fs is not None:
                return fs / 1_000_000
    except Exception:
        return None

    return None

# ======================================================
# MAIN PIPELINE
# ======================================================

def get_filtered_symbols():
    today = _today_et()

    if _stage_is_today(CACHE_FINAL):
        final_syms = _load_stage_symbols(CACHE_FINAL) or []
        logging.info(f"💾 Using cached FINAL: {len(final_syms)}")
        return final_syms

    logging.info("🚀 Starting filtering pipeline")

    price_stage = None

    if _stage_is_today(CACHE_PRICE):
        price_stage = _load_stage_symbols(CACHE_PRICE)
        logging.info(f"💾 Using cached PRICE stage: {len(price_stage)}")

    if price_stage is None:
        if _stage_is_today(CACHE_PREV):
            prev_stage = _load_stage_symbols(CACHE_PREV)
        else:
            syms = get_tradable()
            prev_stage = []
            prev_map = {}

            batch = 200
            for i in range(ceil(len(syms) / batch)):
                chunk = syms[i * batch:(i + 1) * batch]
                closes = get_last_close_bulk(chunk)

                for sym, obj in closes.items():
                    prev_stage.append({
                        "symbol": sym,
                        "prev_close": obj["close"],
                        "bar_date": obj["date"],
                    })
                    prev_map[sym] = obj["close"]

                logging.info(f"⏳ PrevClose batch {i+1}")

            _write_json(CACHE_PREV, {"date": today, "symbols": prev_stage})
            _write_json(PREV_CLOSE_CACHE, prev_map)

        price_stage = [
            x for x in prev_stage
            if MIN_PRICE <= x["prev_close"] <= MAX_PRICE
        ]

        _write_json(CACHE_PRICE, {"date": today, "symbols": price_stage})
        logging.info(f"✅ Price filter complete: {len(price_stage)}")

    # ==================================================
    # FLOAT FILTER (UPDATED)
    # ==================================================

    logging.info("📏 Filtering by float ≤ 10M (threaded)")
    final = []
    total = len(price_stage)
    checked = 0

    MAX_WORKERS = 8
    LOG_EVERY = 50

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(fmp_float_safe, item["symbol"]): item
            for item in price_stage
        }

        for future in as_completed(future_map):
            item = future_map[future]
            checked += 1

            fl = future.result()
            item["float"] = fl

            if fl is None or fl <= MAX_FLOAT:
                final.append(item)

            if checked % LOG_EVERY == 0 or checked == total:
                logging.info(
                    f"📏 Float stage: {checked}/{total} | passed {len(final)}"
                )

    _write_json(CACHE_FINAL, {"date": today, "symbols": final})
    logging.info(f"🏁 FINAL COUNT: {len(final)}")
    return final
