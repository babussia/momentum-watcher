# app/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
import logging

# --- Imports ---
from app.api import routes_hod, routes_overview, routes_news
from app.services.alpaca_ws import run_alpaca_ws
from app.services.alpaca_preload import preload_volume
from app.services.data_cache import reset_loop
from app.services.symbol_filter import get_filtered_symbols  # ✅ main filter
# (You’ll add refresh_daily_symbols later when you automate nightly refresh)

# =====================================================
# INIT
# =====================================================
load_dotenv()
app = FastAPI(title="Momentum Watcher", version="0.1")

# =====================================================
# MIDDLEWARE
# =====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# STATIC FILES & HTML
# =====================================================
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# =====================================================
# ROUTES
# =====================================================
app.include_router(routes_hod.router)
app.include_router(routes_overview.router)
app.include_router(routes_news.router)

# =====================================================
# STARTUP TASKS (Filter + Preload + WebSocket + Daily Reset)
# =====================================================
@app.on_event("startup")
async def on_startup():
    logging.info("🚀 Starting Momentum Watcher startup tasks...")

    loop = asyncio.get_event_loop()

    # 🧠 1. Fetch tickers that match price + float filters
    symbols = await loop.run_in_executor(None, get_filtered_symbols)
    logging.info(f"🧠 Filtered {len(symbols)} tickers for subscription.")

    # 💾 2. Preload volume from 4AM until now
    await loop.run_in_executor(None, preload_volume)

    # 🔌 3. Start live WebSocket and auto daily reset
    asyncio.create_task(run_alpaca_ws())
    asyncio.create_task(reset_loop())

    logging.info("✅ Startup complete — filters, preload, and WebSocket running.")


# =====================================================
# ROOT ROUTE
# =====================================================
@app.get("/")
def index(request: Request):
    """Render main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})
