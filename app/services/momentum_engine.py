# app/services/momentum_engine.py

import time
import logging
from bisect import bisect_left
from collections import defaultdict, deque
from datetime import timedelta
from typing import Deque, Dict, Tuple, Optional

from app.services.data_cache import momentum_events, MAX_MOMENTUM_SYMBOLS

logger = logging.getLogger(__name__)

# =============================================
# CONFIG
# =============================================

FLASH_SPIKE_TRADE_COUNT = 5
MIN_CONSECUTIVE_INCREASES = 3
MIN_BUY_PRICE_MOVE = 0.03        # absolute $ move inside 1s
FLASH_SPIKE_AVG_VOLUME = 60

PROFIT_TRIGGER = 0.03            # +3%
VOLUME_5MIN_THRESHOLD = 1200
SPREAD_THRESHOLD = 0.55          # optional safety filter (only if spread known)

# =============================================
# STATE (runtime only)
# =============================================

recent_trades: Dict[str, Deque[Tuple[object, float, int]]] = defaultdict(deque)  # (ts, price, size) within 1s
price_record: Dict[str, Deque[Tuple[object, float]]] = defaultdict(deque)       # (ts, price) within 5m
volume_window: Dict[str, Deque[Tuple[object, int]]] = defaultdict(deque)        # (ts, size) within 5m

# quotes are ONLY cached (never trigger)
last_spread: Dict[str, float] = {}    # symbol -> spread

# last emitted momentum % per symbol (so we only append a new row when % increases)
last_emitted_pct: Dict[str, float] = {}

# per-symbol event sequence (helps uniqueness if timestamps match)
event_seq: Dict[str, int] = defaultdict(int)

# =============================================
# QUOTE HANDLER (CACHE ONLY)
# =============================================

def on_quote(symbol: str, bid: float, ask: float, size: int, price: float, ts):
    """
    Quotes do NOT trigger momentum.
    They only update last known spread for optional validation.
    """
    try:
        bid = float(bid)
        ask = float(ask)
    except Exception:
        return

    if bid <= 0 or ask <= 0:
        return

    last_spread[symbol] = ask - bid


# =============================================
# TRADE HANDLER (REAL-TIME SIGNAL)
# =============================================

def on_trade(symbol: str, price: float, size: int, ts):
    """
    Trade-driven momentum detection.
    Adds a NEW event row ONLY when this symbol's % increases vs last emitted.
    """

    # -------------------------
    # Hard type safety
    # -------------------------
    try:
        price = float(price)
        size = int(size)
    except Exception:
        return

    if price <= 0 or size <= 0:
        return

    # =============================
    # RECORD RECENT TRADES (1s)
    # =============================
    recent_trades[symbol].append((ts, price, size))

    cutoff_1s = ts - timedelta(milliseconds=1000)
    recent_trades[symbol] = deque(
        t for t in recent_trades[symbol] if t[0] >= cutoff_1s
    )

    trades = recent_trades[symbol]
    number_of_trades_1sec = len(trades)

    if number_of_trades_1sec < FLASH_SPIKE_TRADE_COUNT:
        return

    trade_prices = [p for _, p, _ in trades]

    # =============================
    # RULE 1 — FLASH SPIKE
    # =============================
    subseq = []
    for p in trade_prices:
        i = bisect_left(subseq, p)
        if i < len(subseq):
            subseq[i] = p
        else:
            subseq.append(p)
        if len(subseq) >= MIN_CONSECUTIVE_INCREASES:
            break

    if len(subseq) < MIN_CONSECUTIVE_INCREASES:
        return

    price_diff_1sec = max(trade_prices) - min(trade_prices)
    if price_diff_1sec < MIN_BUY_PRICE_MOVE:
        return

    avg_vol_1sec = sum(sz for _, _, sz in trades) / number_of_trades_1sec
    if avg_vol_1sec < FLASH_SPIKE_AVG_VOLUME:
        return

    # =============================
    # RULE 2 — +3% FROM 5-MIN LOW
    # =============================
    price_record[symbol].append((ts, price))

    cutoff_5m = ts - timedelta(minutes=5)
    price_record[symbol] = deque(
        (t, p) for t, p in price_record[symbol] if t >= cutoff_5m
    )

    prices_5m = [p for _, p in price_record[symbol]]
    if not prices_5m:
        return

    low_price_5min = min(prices_5m)
    if low_price_5min <= 0:
        return

    price_jump = (price - low_price_5min) / low_price_5min  # fraction
    if price_jump < PROFIT_TRIGGER:
        return

    # =============================
    # RULE 3 — 5-MIN VOLUME
    # =============================
    volume_window[symbol].append((ts, size))
    volume_window[symbol] = deque(
        (t, v) for t, v in volume_window[symbol] if t >= cutoff_5m
    )

    vol_5min = sum(v for _, v in volume_window[symbol])
    if vol_5min < VOLUME_5MIN_THRESHOLD:
        return

    # =============================
    # OPTIONAL SPREAD CHECK (only if we have it)
    # =============================
    spread = last_spread.get(symbol)
    if spread is not None and spread > SPREAD_THRESHOLD:
        return

    # =============================
    # NEW BEHAVIOR:
    # only append a NEW ROW if % increased vs last emitted for this symbol
    # =============================
    new_pct = round(price_jump * 100, 2)
    prev_pct = last_emitted_pct.get(symbol)

    # If we already emitted and it didn't increase, do nothing
    if prev_pct is not None and new_pct <= prev_pct:
        return

    # record the last emitted pct
    last_emitted_pct[symbol] = new_pct

    # unique id for frontend (sound triggers only when new row appears)
    event_seq[symbol] += 1
    event_id = f"{symbol}-{int(ts.timestamp()*1000)}-{event_seq[symbol]}"

    # =============================
    # APPEND EVENT (feed)
    # =============================
    snapshot = {
        "event_id": f"{symbol}-{time.time_ns()}",  # ✅ UNIQUE EVENT ID
        "symbol": symbol,
        "price": round(price, 2),
        "chg": new_pct,                    # % from 5m low
        "five_min": new_pct,               # same field (your table has both)
        "volume": int(vol_5min),
        "spread": round(spread, 3) if spread is not None else None,
        "time": ts.strftime("%H:%M:%S"),
        "ts": time.time(),

        # extra debug fields (optional for UI, but great for logs)
        "price_at_detection": round(price, 2),
        "low_price_5min": round(low_price_5min, 2),
        "price_jump": new_pct,
        "vol_5min": int(vol_5min),
        "number_of_trades_1sec": int(number_of_trades_1sec),
        "avg_vol_1sec": float(round(avg_vol_1sec, 2)),
        "price_diff_1sec": float(round(price_diff_1sec, 4)),
    }

    momentum_events.append(snapshot)

    # keep only last N events total
    if len(momentum_events) > MAX_MOMENTUM_SYMBOLS:
        del momentum_events[:-MAX_MOMENTUM_SYMBOLS]

    logger.info(
        f"⚡ MOMENTUM {symbol} +{new_pct:.2f}% | "
        f"price_at_detection={price:.2f}, "
        f"low_price_5min={low_price_5min:.2f}, "
        f"price_jump={new_pct:.2f}%, "
        f"vol_5min={vol_5min}, "
        f"number_of_trades_1sec={number_of_trades_1sec}, "
        f"avg_vol_1sec={avg_vol_1sec:.0f}, "
        f"price_diff_1sec={price_diff_1sec:.2f}"
    )
