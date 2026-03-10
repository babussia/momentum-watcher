from fastapi import APIRouter, HTTPException
from app.services.news_scraper import scrape_stocktitan

router = APIRouter()

@router.get("/{symbol}")
def get_stock_overview(symbol: str):
    data = scrape_stocktitan(symbol)

    if not data:
        return {
            "symbol": symbol,
            "news_title": "",
            "news_url": "",
            "price_impact": "",
            "error": "No news data available"
        }

    return data
