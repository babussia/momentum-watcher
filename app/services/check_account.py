import os, requests

headers = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY")
}

url = "https://api.alpaca.markets/v2/account"

r = requests.get(url, headers=headers)
print(r.status_code)
print(r.json())
