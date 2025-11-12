# app/services/price_reference.py
import requests
from datetime import datetime, timedelta, timezone
from app.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

URL = "https://data.alpaca.markets/v2/stocks/bars"
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    "accept": "application/json"
}

def get_previous_close(symbol: str) -> float | None:
    """
    Fetches the *previous trading day's* last available bar (including after-hours).
    This effectively gives you the previous close price.
    """
    today = datetime.now(timezone.utc)
    bars = []
    days_back = 1

    while not bars and days_back <= 5:
        day = today - timedelta(days=days_back)
        start = day.replace(hour=4, minute=0, second=0, microsecond=0)
        end = day.replace(hour=20, minute=0, second=0, microsecond=0)

        params = {
            "symbols": symbol,
            "timeframe": "1Min",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "adjustment": "raw",
            "feed": "sip",
            "currency": "USD",
            "limit": 10000,
            "sort": "asc"
        }

        r = requests.get(URL, headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        bars = data.get("bars", {}).get(symbol, [])
        days_back += 1

    if not bars:
        print(f"⚠️ No bars found for {symbol} in last 5 days.")
        return None

    prev_close = bars[-1]["c"]
    print(f"📈 {symbol} previous close: {prev_close}")
    return prev_close


if __name__ == "__main__":
    get_previous_close("AAPL")
