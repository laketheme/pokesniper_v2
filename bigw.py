"""
BIG W Australia stock scraper.
Product pages: https://www.bigw.com.au/product/<slug>/p/<id>
BIG W renders some data as JSON inside __NEXT_DATA__ (Next.js).
"""
import json
import re
from bs4 import BeautifulSoup
from loguru import logger

_IN_STOCK = re.compile(r"(add to cart|in.?stock|available now)", re.IGNORECASE)
_OOS = re.compile(r"(out of stock|sold out|unavailable|notify me)", re.IGNORECASE)


def detect_stock(html: str) -> tuple[bool, str]:
    soup = BeautifulSoup(html, "lxml")
    name = _extract_name(soup)

    # ── 1. Next.js hydration data ───────────────────────────────────────────
    next_data = soup.find("script", {"id": "__NEXT_DATA__"})
    if next_data:
        try:
            data = json.loads(next_data.string or "{}")
            availability = _deep_find(data, "availability") or _deep_find(data, "stockLevel")
            if availability:
                av = str(availability).lower()
                if "instock" in av or av in ("true", "1", "available"):
                    return True, _deep_name(data) or name
                if "outofstock" in av or av in ("false", "0", "unavailable"):
                    return False, _deep_name(data) or name
        except (json.JSONDecodeError, TypeError):
            pass

    # ── 2. JSON-LD ──────────────────────────────────────────────────────────
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        txt = script.get_text()
        if "availability" in txt.lower():
            if "InStock" in txt:
                return True, name
            if "OutOfStock" in txt:
                return False, name

    # ── 3. Add-to-cart button ────────────────────────────────────────────────
    for btn in soup.select("button"):
        txt = btn.get_text(strip=True)
        if _IN_STOCK.search(txt):
            if btn.get("disabled"):
                return False, name
            return True, name
        if _OOS.search(txt):
            return False, name

    # ── 4. Text fallback ────────────────────────────────────────────────────
    body = soup.get_text(" ", strip=True)
    if "Add to Cart" in body and "Out of Stock" not in body:
        return True, name
    if _OOS.search(body):
        return False, name

    return False, name


def _extract_name(soup: BeautifulSoup) -> str:
    for sel in ["h1.product-name", "h1[data-testid='product-title']", "h1"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)[:120]
    t = soup.find("title")
    return t.get_text(strip=True).split("|")[0].strip()[:120] if t else "Unknown Product"


def _deep_find(obj, key: str):
    """Recursively search a nested dict/list for the first value of `key`."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _deep_find(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find(item, key)
            if result is not None:
                return result
    return None


def _deep_name(data: dict) -> str | None:
    for key in ("productName", "name", "title"):
        val = _deep_find(data, key)
        if val and isinstance(val, str) and len(val) > 3:
            return val[:120]
    return None
