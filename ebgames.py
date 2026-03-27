"""
EB Games Australia stock scraper.
Product pages: https://www.ebgames.com.au/product/<slug>
"""
import re
from bs4 import BeautifulSoup
from loguru import logger


# Signals that mean IN STOCK
_IN_STOCK_PATTERNS = re.compile(
    r"(add to cart|add to bag|buy now|in stock|available)",
    re.IGNORECASE,
)

# Signals that mean OUT OF STOCK
_OOS_PATTERNS = re.compile(
    r"(out of stock|sold out|unavailable|notify me|coming soon|pre.?order)",
    re.IGNORECASE,
)


def detect_stock(html: str) -> tuple[bool, str]:
    """
    Returns (in_stock: bool, product_name: str).
    """
    soup = BeautifulSoup(html, "lxml")

    # ── Product name ────────────────────────────────────────────────────────
    name = _extract_name(soup)

    # ── 1. Check JSON-LD structured data (most reliable) ────────────────────
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        text = script.get_text()
        if "availability" in text.lower():
            if "InStock" in text:
                return True, name
            if "OutOfStock" in text or "Discontinued" in text:
                return False, name

    # ── 2. Dedicated stock badge / label ────────────────────────────────────
    for selector in [
        ".stock-indicator", ".stock-status", ".availability",
        "[data-availability]", ".product-availability",
    ]:
        el = soup.select_one(selector)
        if el:
            txt = el.get_text(strip=True)
            if _IN_STOCK_PATTERNS.search(txt):
                return True, name
            if _OOS_PATTERNS.search(txt):
                return False, name

    # ── 3. Add-to-cart button ────────────────────────────────────────────────
    for btn in soup.select("button, input[type='submit'], a.btn, a.button"):
        txt = btn.get_text(strip=True)
        if _IN_STOCK_PATTERNS.search(txt) and "cart" in txt.lower():
            disabled = btn.get("disabled") or btn.get("aria-disabled")
            if disabled:
                return False, name
            return True, name
        if _OOS_PATTERNS.search(txt):
            return False, name

    # ── 4. Full-page text fallback ───────────────────────────────────────────
    body = soup.get_text(" ", strip=True)
    if _OOS_PATTERNS.search(body):
        return False, name

    logger.warning("EB Games: could not determine stock for page (fallback=OOS)")
    return False, name


def _extract_name(soup: BeautifulSoup) -> str:
    for sel in ["h1.product-title", "h1.pdp-title", "h1", "[data-product-name]"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)[:120]
    title = soup.find("title")
    if title:
        return title.get_text(strip=True).split("|")[0].strip()[:120]
    return "Unknown Product"
