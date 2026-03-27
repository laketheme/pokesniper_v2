"""
Stock monitor: runs async polling loop over all tracked products.
Uses a semaphore to cap concurrency and asyncio.gather for speed.
"""
import asyncio
from loguru import logger
from app.db.database import get_all_products, update_product_stock, log_alert
from app.scrapers.router import check_product
from app.bot.notifier import send_restock_alert
from app.core.config import settings

# Global semaphore — limits simultaneous outbound requests
_sem: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.max_concurrent_checks)
    return _sem


async def _check_one(product: dict) -> None:
    """Check a single product and send alert if restocked."""
    sem = _get_semaphore()
    async with sem:
        url = product["url"]
        pid = product["id"]
        prev_in_stock = bool(product["in_stock"])
        prev_notified = bool(product["notified"])
        chat_id = product.get("chat_id") or settings.telegram_chat_id

        try:
            in_stock, name = await check_product(url)
        except Exception as exc:
            logger.warning("Check failed for {}: {}", url, exc)
            return

        # ── State machine ────────────────────────────────────────────────
        if in_stock and not prev_in_stock:
            # Transition: OOS → IN STOCK
            logger.info("✅ RESTOCKED: {} ({})", name, url)
            if chat_id:
                await send_restock_alert(chat_id, name, url)
            await update_product_stock(pid, in_stock=True, notified=True, name=name)
            await log_alert(pid, "in_stock")

        elif in_stock and prev_in_stock and not prev_notified:
            # Was in stock before we started (first run) — just update silently
            await update_product_stock(pid, in_stock=True, notified=True, name=name)

        elif not in_stock and prev_in_stock:
            # Transition: IN STOCK → OOS — reset so next restock triggers alert
            logger.info("❌ WENT OOS: {} ({})", name, url)
            await update_product_stock(pid, in_stock=False, notified=False, name=name)
            await log_alert(pid, "out_of_stock")

        else:
            # No change — just update name + last_check
            await update_product_stock(pid, in_stock=in_stock, notified=prev_notified, name=name)


async def run_poll_cycle() -> None:
    """Fetch all products and check them concurrently."""
    products = await get_all_products()
    if not products:
        logger.debug("No products to monitor.")
        return

    logger.info("Polling {} product(s)...", len(products))
    tasks = [asyncio.create_task(_check_one(p)) for p in products]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Poll cycle complete.")
