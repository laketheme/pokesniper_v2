"""
StockBot — FastAPI entry point.

Modes:
  1. WEBHOOK  (production): Telegram pushes updates to /webhook/<token>
  2. POLLING  (dev/fallback): bot polls Telegram for updates via long-polling

The APScheduler runs the stock-check loop in the background regardless of mode.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update

from app.core.config import settings
from app.core.logger import setup_logger  # noqa: F401 – side-effect import
from app.db.database import init_db
from app.bot.handlers import build_application, set_bot_commands
from app.bot.monitor import run_poll_cycle

# ── Globals ───────────────────────────────────────────────────────────────────
_tg_app = None
_scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _tg_app, _scheduler

    logger.info("🚀 StockBot starting up...")

    # 1. DB
    await init_db()

    # 2. Build Telegram application
    _tg_app = build_application()
    await _tg_app.initialize()

    # 3. Register bot commands in Telegram UI
    try:
        await set_bot_commands(settings.telegram_bot_token)
    except Exception as exc:
        logger.warning("Could not set bot commands: {}", exc)

    # 4. Decide: webhook or polling?
    webhook_url = os.getenv("WEBHOOK_URL")  # e.g. https://yourapp.railway.app
    if webhook_url:
        full_url = f"{webhook_url.rstrip('/')}/webhook/{settings.telegram_bot_token}"
        await _tg_app.bot.set_webhook(full_url)
        logger.info("Webhook set to: {}", full_url)
        await _tg_app.start()
    else:
        # Long-polling mode — run in background task
        logger.info("No WEBHOOK_URL set — using long-polling mode.")
        await _tg_app.updater.start_polling(drop_pending_updates=True)
        await _tg_app.start()

    # 5. Start stock polling scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_poll_cycle,
        trigger="interval",
        seconds=settings.poll_interval_seconds,
        id="stock_poll",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Stock polling scheduled every {}s.", settings.poll_interval_seconds
    )

    yield  # ── app is running ──

    # Shutdown
    logger.info("StockBot shutting down...")
    _scheduler.shutdown(wait=False)
    if webhook_url:
        await _tg_app.bot.delete_webhook()
    await _tg_app.stop()
    await _tg_app.shutdown()


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="StockBot",
    description="Australian retail stock monitor with Telegram alerts",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "poll_interval": settings.poll_interval_seconds}


@app.post("/webhook/{token}")
async def telegram_webhook(token: str, request: Request):
    """Receive Telegram updates via webhook."""
    if token != settings.telegram_bot_token:
        return Response(status_code=403)

    data = await request.json()
    update = Update.de_json(data, _tg_app.bot)
    await _tg_app.process_update(update)
    return Response(status_code=200)


@app.post("/poll/trigger")
async def manual_poll():
    """Manually trigger a poll cycle (useful for testing)."""
    asyncio.create_task(run_poll_cycle())
    return {"status": "poll triggered"}
