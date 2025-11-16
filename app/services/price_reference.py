import os, requests, logging
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
FMP_API_KEY = os.getenv("FMP_API_KEY")

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}


def get_previous_close(symbol: str):
    """
    Get PREVIOUS DAY'S CLOSE reliably.
    Fallback order:
      1. Polygon prev close
      2. Alpaca /bars
      3. FMP previousClose
      4. Yahoo Finance
    """

    # 1️⃣ Polygon prev close
    if POLYGON_API_KEY:
        try:
            r = requests.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
                params={"adjusted": "true", "apiKey": POLYGON_API_KEY},
                timeout=4,
            )
            if r.ok:
                data = r.json()
                if data.get("results"):
                    close = data["results"][0].get("c")
                    if close:
                        logging.info(f"📡 {symbol} prev close from Polygon: {close}")
                        return close
        except:
            pass

    # 2️⃣ Alpaca bars fallback
    try:
        url = "https://data.alpaca.markets/v2/stocks/bars"
        r = requests.get(
            url,
            headers=HEADERS,
            params={"symbols": symbol, "timeframe": "1Day", "limit": 2, "feed": "sip"},
            timeout=4,
        )
        if r.ok:
            bars = r.json().get("bars", {}).get(symbol, [])
            if len(bars) >= 2:
                close = bars[-2].get("c")
                if close:
                    logging.info(f"📊 {symbol} prev close from Alpaca bars: {close}")
                    return close
    except:
        pass

    # 3️⃣ FMP fallback
    if FMP_API_KEY:
        try:
            r = requests.get(
                f"https://financialmodelingprep.com/api/v3/quote/{symbol}?apikey={FMP_API_KEY}",
                timeout=4,
            )
            if r.ok:
                data = r.json()
                if isinstance(data, list) and data:
                    close = data[0].get("previousClose")
                    if close:
                        logging.info(f"💾 {symbol} prev close from FMP: {close}")
                        return close
        except:
            pass

    # 4️⃣ Yahoo Finance ultimate fallback
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d",
            timeout=4,
        )
        if r.ok:
            closes = (
                r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            )
            if len(closes) >= 2 and closes[-2]:
                close = closes[-2]
                logging.info(f"🌐 {symbol} prev close from Yahoo: {close}")
                return close
    except:
        pass

    logging.warning(f"⚠️ Could not find previous close for {symbol}")
    return None
