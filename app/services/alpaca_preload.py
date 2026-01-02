import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import aiohttp
import asyncio

from app.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from app.services.data_cache import cumulative_volume


async def preload_volume():
    logging.info("📊 Preloading volume since 4 AM ET...")

    # ----------------------------------------------------------
    # Load cached filtered tickers (DO NOT RUN FILTER AGAIN)
    # ----------------------------------------------------------
    from app.services.data_cache import load_cached_filtered_tickers
    raw_symbols = load_cached_filtered_tickers()

    if not raw_symbols:
        logging.warning("⚠️ No cached tickers — preload skipped.")
        return

    # raw_symbols is list of dicts → extract ["symbol"]
    symbols = [
        s["symbol"] if isinstance(s, dict) else s
        for s in raw_symbols
    ]

    logging.info(f"📦 Preloading volume for {len(symbols)} symbols")

    # ----------------------------------------------------------
    # Build timestamps (4AM ET → now)
    # ----------------------------------------------------------
    ET = ZoneInfo("America/New_York")
    now_et = datetime.now(ET)

    start_et = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
    start_utc = start_et.astimezone(timezone.utc).isoformat()
    end_utc = now_et.astimezone(timezone.utc).isoformat()

    # Alpaca allows 50 symbols per request
    batches = [symbols[i:i + 50] for i in range(0, len(symbols), 50)]

    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }

    # ----------------------------------------------------------
    # Request historical bars
    # ----------------------------------------------------------
    async with aiohttp.ClientSession() as session:
        for batch in batches:
            params = {
                "symbols": ",".join(batch),
                "timeframe": "1Min",
                "start": start_utc,
                "end": end_utc,
                "feed": "sip",
                "limit": 10000,
            }

            try:
                async with session.get(
                    "https://data.alpaca.markets/v2/stocks/bars",
                    headers=headers,
                    params=params
                ) as r:

                    if r.status != 200:
                        text = await r.text()
                        logging.error(
                            f"❌ Error fetching batch {batch[:3]}... "
                            f"HTTP {r.status} → {text}"
                        )
                        continue

                    data = await r.json()
                    bars_data = data.get("bars", {})

                    if not bars_data:
                        continue

                    for symbol, bars in bars_data.items():
                        total = sum(b.get("v", 0) for b in bars)
                        cumulative_volume[symbol] = total

            except Exception as e:
                logging.error(f"❌ Exception during preload for {batch[:3]}: {e}")

            await asyncio.sleep(0.05)  # small safety delay

    logging.info("✅ Preload complete — volumes ready for live updates.")
