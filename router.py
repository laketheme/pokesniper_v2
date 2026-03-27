from urllib.parse import urlparse
from loguru import logger
from app.scrapers import ebgames, bigw, target_au, generic
from app.scrapers.base import fetch_page
from app.core.config import settings


_SCRAPER_MAP = {
    "ebgames.com.au": ebgames,
    "www.ebgames.com.au": ebgames,
    "bigw.com.au": bigw,
    "www.bigw.com.au": bigw,
    "target.com.au": target_au,
    "www.target.com.au": target_au,
}


def _pick_scraper(url: str):
    host = urlparse(url).netloc.lower()
    return _SCRAPER_MAP.get(host, generic)


def detect_retailer(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "ebgames" in host:
        return "EB Games"
    if "bigw" in host:
        return "BIG W"
    if "target.com.au" in host:
        return "Target AU"
    return urlparse(url).netloc


async def check_product(url: str) -> tuple[bool, str]:
    """
    Fetch a product page and return (in_stock, product_name).
    Raises on network/HTTP errors after retries.
    """
    proxy = settings.proxy_url or None
    html, status = await fetch_page(url, proxy=proxy)
    scraper = _pick_scraper(url)
    in_stock, name = scraper.detect_stock(html)
    logger.debug("{} → in_stock={} name='{}'", url, in_stock, name)
    return in_stock, name
