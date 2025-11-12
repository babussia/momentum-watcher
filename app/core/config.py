import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Use SIP feed for real-time, full-market data
DATA_STREAM_URL = os.getenv(
    "DATA_STREAM_URL",
    "wss://stream.data.alpaca.markets/v2/sip"
)
