from collections import defaultdict, deque

# ================================
# Momentum State (runtime only)
# ================================

# trade history (for flash spike rule)
recent_trades = defaultdict(deque)   # symbol -> deque[(ts, price, size)]

# rolling price history (5-min window)
price_record = defaultdict(deque)    # symbol -> deque[(ts, price)]

# rolling volume window (5-min)
volume_window = defaultdict(deque)   # symbol -> deque[(ts, size)]

# symbols currently being processed (dedupe)
processing_symbols = set()
