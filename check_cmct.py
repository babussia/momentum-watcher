import os
import requests
from dotenv import load_dotenv

load_dotenv()

symbol = "aplm"

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")

alpaca_headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

print(f"=== Checking {symbol} ===\n")

# 1️⃣ Alpaca snapshot
try:
    r = requests.get(
        f"https://data.alpaca.markets/v2/stocks/{symbol}/snapshot",
        headers=alpaca_headers,
        timeout=5,
    )
    print("Alpaca snapshot status:", r.status_code)
    if r.ok:
        snap = r.json().get("snapshot", {})
        print("Alpaca dailyBar:", snap.get("dailyBar"))
    else:
        print(r.text)
except Exception as e:
    print("Alpaca error:", e)

# 2️⃣ Alpaca /bars fallback (new part!)
try:
    bars_url = "https://data.alpaca.markets/v2/stocks/bars"
    params = {
        "symbols": symbol,
        "timeframe": "1Day",
        "limit": 2,
        "feed": "sip",
    }
    r_bars = requests.get(bars_url, headers=alpaca_headers, params=params, timeout=5)
    print("\nAlpaca /bars status:", r_bars.status_code)
    if r_bars.ok:
        bars = r_bars.json().get("bars", {}).get(symbol, [])
        print(f"Alpaca /bars data (len={len(bars)}):", bars[-2:] if bars else "None")
    else:
        print(r_bars.text)
except Exception as e:
    print("Alpaca /bars error:", e)

# 3️⃣ Polygon previous close
if POLYGON_API_KEY:
    try:
        r = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
            params={"adjusted": "true", "apiKey": POLYGON_API_KEY},
            timeout=5,
        )
        print("\nPolygon status:", r.status_code)
        if r.ok:
            print(r.json())
        else:
            print(r.text)
    except Exception as e:
        print("Polygon error:", e)

# 4️⃣ FMP quote
if FMP_API_KEY:
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}",
            timeout=5,
        )
        print("\nFMP status:", r.status_code)
        if r.ok:
            print(r.json())
        else:
            print(r.text)
    except Exception as e:
        print("FMP error:", e)

print("\n✅ Done.")
