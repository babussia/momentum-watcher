from app.services.price_reference import get_previous_close
import os, requests
from dotenv import load_dotenv
load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

symbol = "TRUG"

# use your production get_previous_close()
prev_close = get_previous_close(symbol)

# current price from Alpaca
r = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", headers=headers)
quote = r.json().get("quote", {})
last_price = quote.get("ap") or quote.get("bp")

print(f"{symbol} last price: {last_price}")
print(f"{symbol} previous close: {prev_close}")
if last_price and prev_close:
    chg = ((last_price - prev_close) / prev_close) * 100
    print(f"Change: {chg:+.2f}%")

