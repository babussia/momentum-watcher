# app/services/alpaca_ws.py
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

import websockets

from app.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from app.services.data_cache import update_trade, update_quote
from app.services.momentum_engine import on_trade

# ============================
# CONFIG
# ============================
ET = ZoneInfo("America/New_York")
CACHE_PATH = "cache/filtered_symbols.json"

WS_URL = "wss://stream.data.alpaca.markets/v2/sip"

CHUNK_SIZE = 200
SUBSCRIBE_SLEEP = 0.35

MAX_QUEUE_SIZE = 50_000
WORKER_COUNT = 4

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("alpaca_ws")


# ============================
# HELPERS
# ============================
def parse_alpaca_ts(ts: Any) -> datetime:
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:  # nanoseconds
                return datetime.fromtimestamp(ts / 1e9, tz=timezone.utc).astimezone(ET)
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET)

        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ET)
    except Exception:
        pass

    return datetime.now(ET)


async def load_cached_symbols() -> list[str]:
    if not os.path.exists(CACHE_PATH):
        logger.warning("⚠️ No cached filtered symbols found.")
        return []

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)

        if cache.get("date") != datetime.now(ET).date().isoformat():
            logger.warning("⚠️ Cached symbols from previous date — ignoring.")
            return []

        symbols = [
            item["symbol"]
            for item in cache.get("symbols", [])
            if isinstance(item, dict) and item.get("symbol")
        ]

        logger.info(f"💾 Loaded {len(symbols)} cached tickers for today.")
        return symbols

    except Exception as e:
        logger.error(f"❌ Failed loading symbol cache: {e}")
        return []


# ============================
# EVENT PIPELINE
# ============================
async def ws_reader(ws: websockets.WebSocketClientProtocol, q: asyncio.Queue):
    async for raw_msg in ws:
        try:
            payload = json.loads(raw_msg)
            if not isinstance(payload, list):
                continue

            for event in payload:
                if q.full():
                    try:
                        _ = q.get_nowait()
                        q.task_done()
                    except Exception:
                        pass

                await q.put(event)

        except Exception as e:
            logger.error(f"⚠️ Reader parse error: {e}")


async def event_worker(name: str, q: asyncio.Queue):
    while True:
        event = await q.get()
        try:
            etype = event.get("T")
            symbol = event.get("S")
            if not symbol:
                continue

            ts = parse_alpaca_ts(event.get("t"))

            # ======================
            # TRADE → HOD + MOMENTUM
            # ======================
            if etype == "t":
                try:
                    price = float(event.get("p", 0))
                    size = int(event.get("s") or event.get("v") or event.get("z") or 0)
                except Exception:
                    continue

                if price <= 0 or size <= 0:
                    continue

                update_trade(symbol, price, size)
                on_trade(symbol=symbol, price=price, size=size, ts=ts)

            # ======================
            # QUOTE → CACHE ONLY
            # ======================
            elif etype == "q":
                try:
                    bid = float(event.get("bp") or 0)
                    ask = float(event.get("ap") or 0)
                except Exception:
                    continue

                if bid <= 0 or ask <= 0:
                    continue

                update_quote(symbol, bid, ask, ts)

        except Exception as e:
            logger.error(f"⚠️ Worker {name} failed: {e}")
        finally:
            q.task_done()


# ============================
# MAIN LOOP
# ============================
async def run_alpaca_ws():
    symbols = await load_cached_symbols()
    if not symbols:
        logger.warning("⚠️ No cached list — using fallback.")
        symbols = ["AAPL", "TSLA", "NVDA", "AMD", "PLTR"]

    q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

    for i in range(WORKER_COUNT):
        asyncio.create_task(event_worker(f"W{i+1}", q))

    backoff = 1.0
    while True:
        try:
            logger.info(f"🌍 Connecting to {WS_URL}")

            async with websockets.connect(
                WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_queue=None,
            ) as ws:
                logger.info("🔌 Connected to Alpaca WebSocket")

                await ws.send(json.dumps({
                    "action": "auth",
                    "key": ALPACA_API_KEY,
                    "secret": ALPACA_SECRET_KEY,
                }))
                logger.info("✅ Auth sent")

                for i in range(0, len(symbols), CHUNK_SIZE):
                    chunk = symbols[i:i + CHUNK_SIZE]
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "trades": chunk,
                        "quotes": chunk,
                    }))
                    await asyncio.sleep(SUBSCRIBE_SLEEP)

                logger.info(f"📡 Subscribed to {len(symbols)} tickers.")

                backoff = 1.0
                await ws_reader(ws, q)

        except Exception as e:
            logger.error(f"❌ WebSocket disconnected: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.8, 30.0)
            logger.info("♻️ Reconnecting...")
