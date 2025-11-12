# app/services/alpaca_ws.py
import asyncio
import json
import logging
import websockets
from datetime import datetime
import os

from app.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from app.services.data_cache import update_trade

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

CACHE_PATH = "cache/filtered_symbols.json"


async def load_cached_symbols():
    """Load cached filtered symbols from file if available."""
    if not os.path.exists(CACHE_PATH):
        logging.warning("⚠️ No cached symbol list found.")
        return []

    try:
        import json
        from zoneinfo import ZoneInfo
        from datetime import datetime

        ET = ZoneInfo("America/New_York")

        with open(CACHE_PATH, "r") as f:
            cache = json.load(f)
        cache_date = cache.get("date")
        today = datetime.now(ET).date().isoformat()

        if cache_date == today:
            symbols = cache.get("symbols", [])
            logging.info(f"💾 Loaded {len(symbols)} cached filtered tickers for today.")
            return symbols
        else:
            logging.warning("⚠️ Cached symbols are from a previous day — skipping.")
            return []
    except Exception as e:
        logging.error(f"❌ Error loading cached symbols: {e}")
        return []


async def run_alpaca_ws():
    """Connect to Alpaca WebSocket and stream live trades from SIP feed."""
    url = "wss://stream.data.alpaca.markets/v2/sip"
    print("🌍 Connecting to", url)

    try:
        async with websockets.connect(url) as ws:
            logging.info("🔌 Connected to Alpaca WebSocket")

            # Authenticate
            auth_msg = {
                "action": "auth",
                "key": ALPACA_API_KEY,
                "secret": ALPACA_SECRET_KEY,
            }
            await ws.send(json.dumps(auth_msg))
            logging.info("✅ Auth message sent")

            # Load cached symbols
            symbols = await load_cached_symbols()
            if not symbols:
                logging.warning("⚠️ Using fallback symbol list (cache empty).")
                symbols = ["AAPL", "TSLA", "NVDA", "AMD", "PLTR", "GME"]

            # Subscribe (chunked in groups of 200 for SIP feed stability)
            CHUNK_SIZE = 200
            for i in range(0, len(symbols), CHUNK_SIZE):
                chunk = symbols[i : i + CHUNK_SIZE]
                sub_msg = {"action": "subscribe", "trades": chunk}
                await ws.send(json.dumps(sub_msg))
                await asyncio.sleep(0.3)  # avoid rate-limit bursts

            logging.info(f"📡 Subscribed to {len(symbols)} tickers.")

            # Main WebSocket loop
            async for msg in ws:
                try:
                    data = json.loads(msg)
                    if isinstance(data, list):
                        for event in data:
                            if event.get("T") == "t":  # trade event
                                symbol = event["S"]
                                price = event["p"]
                                volume = (
                                    event.get("s")
                                    or event.get("v")
                                    or event.get("z")
                                    or 0
                                )
                                update_trade(symbol, price, volume)
                except Exception as e:
                    logging.error(f"⚠️ Error processing message: {e}")

    except Exception as e:
        logging.error(f"❌ WebSocket connection error: {e}")
        await asyncio.sleep(5)
        logging.info("♻️ Reconnecting...")
        await run_alpaca_ws()
