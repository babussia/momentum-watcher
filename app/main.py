from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import asyncio
import logging
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

# ROUTES
from app.api import routes_hod, routes_overview, routes_news
from app.api.routes_news_overviews_stock import router as news_overview_router
from app.api.routes_momentum import router as momentum_router   # ✅ IMPORT ONLY
from app.api.routes_ahk import router as ahk_router
from fastapi.responses import FileResponse

from app.services.symbol_filter import get_filtered_symbols
from app.services.price_reference import load_prev_closes
from app.services.alpaca_preload import preload_volume
from app.services.alpaca_ws import run_alpaca_ws
from app.services.data_cache import reset_loop

# =========================
# INIT
# =========================
load_dotenv()

ET = ZoneInfo("America/New_York")
CACHE_FILE = "cache/filtered_symbols.json"

app = FastAPI(title="Momentum Watcher", version="0.1")  # ✅ app DEFINED HERE

# =========================
# MIDDLEWARE
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# STATIC / TEMPLATES
# =========================
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# =========================
# ROUTERS (AFTER app EXISTS)
# =========================
app.include_router(routes_hod.router)
app.include_router(routes_overview.router, prefix="/overview")
app.include_router(routes_news.router, prefix="/news")
app.include_router(news_overview_router, prefix="/news-overview")
app.include_router(momentum_router, prefix="/momentum") 
app.include_router(ahk_router)


# =========================
# STARTUP
# =========================
def cached_filter_exists():
    if not os.path.exists(CACHE_FILE):
        return False
    try:
        data = json.load(open(CACHE_FILE))
        return data.get("date") == datetime.now(ET).date().isoformat()
    except Exception:
        return False


@app.on_event("startup")
async def on_startup():
    logging.info("🚀 Starting Momentum Watcher startup tasks...")

    loop = asyncio.get_event_loop()

    load_prev_closes()
    logging.info("💾 Loaded previous close cache.")

    if cached_filter_exists():
        logging.info("💾 Using cached symbols.")
    else:
        logging.info("🧠 Running filtering pipeline...")
        await loop.run_in_executor(None, get_filtered_symbols)
        logging.info("🧠 Filtering complete.")

    await preload_volume()
    asyncio.create_task(run_alpaca_ws())
    asyncio.create_task(reset_loop())

    logging.info("✅ Startup complete — ready.")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("app/static/favicon.ico")