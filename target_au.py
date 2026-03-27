"""
Target Australia stock scraper.
Product pages: https://www.target.com.au/p/<slug>/<id>
Target AU is a React SPA; product data lives in window.__INITIAL_STATE__ or JSON-LD.
"""
import json
import re
from bs4 import BeautifulSoup
from loguru import logger

_IN_STOCK = re.compile(r"(add to (cart|bag)|in.?stock|available)", re.IGNORECASE)
_OOS = re.compile(r"(out of stock|sold out|unavailable|notify me|pre.?order)", re.IGNORECASE)

# Target uses a specific data attribute
_AVAILABILITY_ATTR = re.compile(r'"availability"\s*:\s*"([^"]+)"', re.IGNORECASE)
_STOCK_LEVEL = re.compile(r'"stockLevel"\s*:\s*(\d+)', re.IGNORECASE)


def detect_stock(html: str) -> tuple[bool, str]:
    soup = BeautifulSoup(html, "lxml")
    name = _extract_name(soup)

    # ── 1. Inline JSON state (common in AU Target) ───────────────────────────
    for script in soup.find_all("script"):
        txt = script.string or ""
        if "availability" in txt.lower() or "stockLevel" in txt:
            # Try to extract availability
            av_match = _AVAILABILITY_ATTR.search(txt)
            if av_match:
                av = av_match.group(1).lower()
                if "instock" in av or av == "available":
                    return True, name
                if "outofstock" in av or av in ("unavailable", "discontinued"):
                    return False, name
            # Try stock level number
            sl_match = _STOCK_LEVEL.search(txt)
            if sl_match:
                level = int(sl_match.group(1))
                return level > 0, name

    # ── 2. JSON-LD ──────────────────────────────────────────────────────────
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, list):
                data = data[0] if data else {}
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            av = offers.get("availability", "")
            if "InStock" in av:
                return True, data.get("name", name)[:120]
            if "OutOfStock" in av:
                return False, data.get("name", name)[:120]
        except (json.JSONDecodeError, AttributeError):
            pass

    # ── 3. Button / badge ────────────────────────────────────────────────────
    for btn in soup.select("button, [data-testid*='add'], [class*='add-to-cart']"):
        txt = btn.get_text(strip=True)
        if _IN_STOCK.search(txt):
            if btn.get("disabled") or "disabled" in btn.get("class", []):
                return False, name
            return True, name
        if _OOS.search(txt):
            return False, name

    # ── 4. Full text fallback ────────────────────────────────────────────────
    body = soup.get_text(" ", strip=True)
    if _OOS.search(body):
        return False, name

    logger.warning("Target AU: stock undetermined for page (fallback OOS)")
    return False, name


def _extract_name(soup: BeautifulSoup) -> str:
    for sel in ["h1[data-testid='product-title']", "h1.product-title", "h1"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)[:120]
    t = soup.find("title")
    return t.get_text(strip=True).split("|")[0].strip()[:120] if t else "Unknown Product"
