import logging
from datetime import datetime, timedelta, timezone
import requests
from zoneinfo import ZoneInfo
from app.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from app.services.data_cache import cumulative_volume  # ✅ shared memory


def preload_volume():
    """Prefetch cumulative volume from 4 AM ET to now for all tracked tickers."""
    logging.info("📊 Preloading volume since 4 AM...")

    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "PLTR", "GME"]
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }
    url = "https://data.alpaca.markets/v2/stocks/bars"

    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)
    start_et = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
    start_utc = start_et.astimezone(timezone.utc).isoformat()
    end_utc = now_et.astimezone(timezone.utc).isoformat()

    for symbol in tickers:
        try:
            params = {
                "symbols": symbol,
                "timeframe": "1Min",
                "start": start_utc,
                "end": end_utc,
                "feed": "sip",
                "limit": 10000,
            }

            r = requests.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()

            bars = data.get("bars", {}).get(symbol, [])
            if not bars:
                logging.warning(f"⚠️ No volume data for {symbol}")
                continue

            total_vol = sum(b.get("v", 0) for b in bars)
            cumulative_volume[symbol] = total_vol  # ✅ shared dictionary

            logging.info(f"✅ {symbol} preload volume: {total_vol:,}")

        except Exception as e:
            logging.error(f"❌ Failed to preload {symbol}: {e}")

    logging.info("✅ Preload complete — volumes ready for live updates.")

