import json
import os

PREV_CLOSE_CACHE = "cache/prev_close_cache.json"

_prev_closes = {}

def load_prev_closes():
    global _prev_closes
    if os.path.exists(PREV_CLOSE_CACHE):
        with open(PREV_CLOSE_CACHE, "r") as f:
            _prev_closes = json.load(f)
    else:
        _prev_closes = {}

def get_prev_close(symbol):
    return _prev_closes.get(symbol)
