from datetime import datetime, timezone
import httpx
from loguru import logger
from app.core.config import settings

_API_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def send_restock_alert(chat_id: str, product_name: str, url: str) -> bool:
    """Send an in-stock notification. Returns True on success."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = (
        "🟢 *BACK IN STOCK!*\n\n"
        f"📦 *{_escape(product_name)}*\n"
        f"🏪 {_escape(_retailer_from_url(url))}\n"
        f"🕐 {now}\n\n"
        f"🔗 [View Product]({url})"
    )
    return await _send(chat_id, text)


async def send_message(chat_id: str, text: str) -> bool:
    return await _send(chat_id, text, parse_mode=None)


async def send_markdown(chat_id: str, text: str) -> bool:
    return await _send(chat_id, text)


async def _send(chat_id: str, text: str, parse_mode: str | None = "Markdown") -> bool:
    payload: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{_API_BASE}/sendMessage", json=payload)
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Telegram send failed: {}", exc)
        return False


def _retailer_from_url(url: str) -> str:
    from app.scrapers.router import detect_retailer
    return detect_retailer(url)


def _escape(text: str) -> str:
    """Minimal Markdown V1 escape."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text
