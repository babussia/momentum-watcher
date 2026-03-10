import logging
import requests
from bs4 import BeautifulSoup
import datetime
import time

BASE_URL = "https://www.stocktitan.net/overview/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ======================
# In-memory caches
# ======================
_OVERVIEW_CACHE = {}   # (symbol, date) -> fundamentals
_NEWS_CACHE = {}       # symbol -> latest article data


def _today_key():
    return datetime.date.today().isoformat()


# =========================================
# Main scraper (working logic + caching)
# =========================================
def scrape_stocktitan(symbol: str):
    today = _today_key()
    overview_cache_key = (symbol, today)

    logging.info(f"📰 Checking StockTitan for {symbol}")

    # Always hit overview page to get latest headline
    overview_url = f"{BASE_URL}{symbol}"
    r = requests.get(overview_url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    latest_news = soup.select_one("div.st-panel-body.news-list div.news-item")
    if not latest_news:
        return None

    news_link_tag = latest_news.select_one("h3.news-title a")
    news_url = (
        "https://www.stocktitan.net" + news_link_tag["href"]
        if news_link_tag else ""
    )
    news_title = news_link_tag.get_text(strip=True) if news_link_tag else ""

    news_date_tag = latest_news.select_one("div.news-time")
    news_date = (
        news_date_tag["title"]
        if news_date_tag and news_date_tag.has_attr("title")
        else ""
    )

    price_impact = (
        latest_news.select_one("div.price-impact").get_text(strip=True)
        if latest_news.select_one("div.price-impact") else ""
    )

    # ======================
    # NEWS CACHE CHECK
    # ======================
    cached_news = _NEWS_CACHE.get(symbol)

    if cached_news and cached_news["news_url"] == news_url:
        logging.info(f"⚡ News cache hit for {symbol}")

        fundamentals = _OVERVIEW_CACHE.get(overview_cache_key)
        if fundamentals:
            logging.info(f"⚡ Overview cache hit for {symbol}")

        return {
            "symbol": symbol,
            **(fundamentals or {}),
            **cached_news,
        }

    # ======================
    # FETCH FULL ARTICLE
    # ======================
    logging.info(f"🆕 New headline detected for {symbol}")

    news_content = ""
    news_time = ""
    summary_text = ""

    stock_data = {
        field.lower().replace(" ", "_"): "N/A"
        for field in [
            "Market Cap", "Float", "Insiders Ownership",
            "Institutions Ownership", "Short Percent",
            "Industry", "Sector", "Website",
            "Country", "City"
        ]
    }

    if news_url:
        news_page = requests.get(news_url, headers=HEADERS, timeout=10)
        if news_page.status_code == 200:
            news_soup = BeautifulSoup(news_page.text, "html.parser")

            content_tag = news_soup.select_one("div.news-content")
            if content_tag:
                news_content = content_tag.get_text(strip=True)

            time_tag = news_soup.select_one("time[datetime]")
            if time_tag:
                news_time = time_tag.get_text(strip=True)

            summary_tag = news_soup.select_one("div.news-card-summary #summary")
            if summary_tag:
                summary_text = summary_tag.get_text(strip=True)

            # ✅ FUNDAMENTALS (this is why your original code works)
            for div in news_soup.select("div.news-list-item.stock-data"):
                label = div.find("label")
                if not label:
                    continue

                field_name = label.get_text(strip=True)
                key = field_name.lower().replace(" ", "_")

                if key not in stock_data:
                    continue

                if field_name == "Website":
                    a_tag = div.find("a")
                    stock_data[key] = a_tag["href"] if a_tag else "N/A"
                else:
                    span = div.find("span", class_="d-flex")
                    stock_data[key] = span.get_text(strip=True) if span else "N/A"

    # ======================
    # CACHE WRITE
    # ======================
    if any(v not in ("N/A", "", None) for v in stock_data.values()):
        _OVERVIEW_CACHE[overview_cache_key] = stock_data
        logging.info(f"💾 Cached overview for {symbol}")

    _NEWS_CACHE[symbol] = {
        "news_title": news_title,
        "news_url": news_url,
        "news_date": news_date,
        "news_time": news_time,
        "price_impact": price_impact,
        "news_content": news_content,
        "summary": summary_text,
        "cached_at": time.time(),
    }

    return {
        "symbol": symbol,
        **stock_data,
        **_NEWS_CACHE[symbol],
    }
