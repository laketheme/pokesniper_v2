"""
Generic stock scraper — works on most English-language retail pages.
Used as fallback for retailers without a dedicated scraper.
"""
import json
import re
from bs4 import BeautifulSoup
from loguru import logger

_IN_STOCK = re.compile(
    r"\b(add to (cart|bag|basket|trolley)|buy now|in stock|available now|in-stock)\b",
    re.IGNORECASE,
)
_OOS = re.compile(
    r"\b(out of stock|sold out|unavailable|notify me when|back in stock|pre.?order|coming soon)\b",
    re.IGNORECASE,
)


def detect_stock(html: str) -> tuple[bool, str]:
    soup = BeautifulSoup(html, "lxml")
    name = _extract_name(soup)

    # 1. JSON-LD schema.org
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, list):
                data = data[0] if data else {}
            offers = data.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            av = offers.get("availability", "")
            if "InStock" in av:
                return True, data.get("name", name)[:120]
            if "OutOfStock" in av or "Discontinued" in av:
                return False, data.get("name", name)[:120]
        except Exception:
            pass

    # 2. Meta tags
    meta = soup.find("meta", {"property": "product:availability"}) or \
           soup.find("meta", {"name": "availability"})
    if meta:
        content = (meta.get("content") or "").lower()
        if "in stock" in content:
            return True, name
        if "out of stock" in content or "oos" in content:
            return False, name

    # 3. Buttons
    for btn in soup.select("button, input[type='submit']"):
        txt = btn.get_text(strip=True)
        if _IN_STOCK.search(txt):
            if btn.get("disabled"):
                return False, name
            return True, name
        if _OOS.search(txt):
            return False, name

    # 4. Stock badge / label elements
    for sel in [
        ".stock", ".availability", ".stock-status", ".in-stock",
        ".out-of-stock", "[class*='stock']", "[class*='availability']",
        "[data-stock]", "[data-availability]",
    ]:
        el = soup.select_one(sel)
        if el:
            txt = el.get_text(strip=True)
            if _IN_STOCK.search(txt):
                return True, name
            if _OOS.search(txt):
                return False, name

    # 5. Broad body text
    body = soup.get_text(" ", strip=True)
    has_cart = bool(_IN_STOCK.search(body))
    has_oos  = bool(_OOS.search(body))

    if has_oos:
        return False, name
    if has_cart:
        return True, name

    logger.debug("Generic scraper: stock undetermined (fallback OOS)")
    return False, name


def _extract_name(soup: BeautifulSoup) -> str:
    for sel in ["h1.product-title", "h1.product-name", "h1"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)[:120]
    t = soup.find("title")
    return t.get_text(strip=True).split("|")[0].strip()[:120] if t else "Unknown Product"
