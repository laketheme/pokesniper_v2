"""
Telegram Bot command handlers.
Supports both webhook (production) and long-polling (dev) modes.
"""
import asyncio
from urllib.parse import urlparse
from loguru import logger
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from app.core.config import settings
from app.db.database import add_product, remove_product, list_products
from app.scrapers.router import check_product, detect_retailer


# ── Helpers ──────────────────────────────────────────────────────────────────

def _chat(update: Update) -> str:
    return str(update.effective_chat.id)


def _user(update: Update) -> str:
    u = update.effective_user
    return str(u.id) if u else "unknown"


def _valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False


# ── Command handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *Stock Monitor Bot*\n\n"
        "Track Australian retail products for restocks.\n\n"
        "*Commands:*\n"
        "/add `<url>` — start tracking a product\n"
        "/remove `<url>` — stop tracking\n"
        "/list — show all tracked products\n"
        "/status — check stock right now\n"
        "/help — show this message",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, ctx)


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat(update)
    user_id = _user(update)

    if not ctx.args:
        await update.message.reply_text(
            "Usage: /add `https://www.ebgames.com.au/product/...`",
            parse_mode="Markdown",
        )
        return

    url = ctx.args[0].strip()
    if not _valid_url(url):
        await update.message.reply_text("❌ That doesn't look like a valid URL.")
        return

    msg = await update.message.reply_text("🔍 Checking product...")

    try:
        in_stock, name = await check_product(url)
        retailer = detect_retailer(url)
    except Exception as exc:
        await msg.edit_text(f"❌ Could not fetch product page.\n`{exc}`", parse_mode="Markdown")
        return

    row_id = await add_product(url, name, retailer, user_id, chat_id)
    if row_id is None:
        await msg.edit_text("⚠️ That product is already being tracked.")
        return

    stock_str = "🟢 In Stock" if in_stock else "🔴 Out of Stock"
    await msg.edit_text(
        f"✅ *Added!*\n\n"
        f"📦 {name}\n"
        f"🏪 {retailer}\n"
        f"📊 Current status: {stock_str}\n\n"
        f"I'll notify you the moment it restocks!",
        parse_mode="Markdown",
    )
    logger.info("Added product: {} ({})", name, url)


async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat(update)

    if not ctx.args:
        await update.message.reply_text(
            "Usage: /remove `<url>`  — or use /list to see tracked URLs.",
            parse_mode="Markdown",
        )
        return

    url = ctx.args[0].strip()
    removed = await remove_product(url, chat_id)
    if removed:
        await update.message.reply_text("🗑️ Product removed from tracking.")
    else:
        await update.message.reply_text("⚠️ Product not found in your tracking list.")


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat(update)
    products = await list_products(chat_id)

    if not products:
        await update.message.reply_text("📭 You're not tracking any products yet.\n\nUse /add `<url>` to start.", parse_mode="Markdown")
        return

    lines = [f"📋 *Tracking {len(products)} product(s):*\n"]
    for i, p in enumerate(products, 1):
        stock_icon = "🟢" if p["in_stock"] else "🔴"
        lines.append(
            f"{i}\\. {stock_icon} [{_escape_md(p['name'])}]({p['url']})\n"
            f"    🏪 {p['retailer']} \\| Last: {p['last_check'] or 'never'}\n"
        )

    # Telegram messages max 4096 chars — chunk if needed
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n_...truncated_"

    await update.message.reply_text(text, parse_mode="MarkdownV2", disable_web_page_preview=True)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Trigger an immediate check for all products."""
    from app.bot.monitor import run_poll_cycle
    msg = await update.message.reply_text("⚡ Running stock check now...")
    await run_poll_cycle()
    await msg.edit_text("✅ Stock check complete. You'll be notified of any changes.")


async def unknown_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("❓ Unknown command. Type /help for available commands.")


# ── Bot factory ───────────────────────────────────────────────────────────────

def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    return app


async def set_bot_commands(token: str) -> None:
    import httpx
    commands = [
        {"command": "start",  "description": "Welcome message"},
        {"command": "add",    "description": "Track a product URL"},
        {"command": "remove", "description": "Stop tracking a product"},
        {"command": "list",   "description": "List all tracked products"},
        {"command": "status", "description": "Run an immediate stock check"},
        {"command": "help",   "description": "Show help"},
    ]
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/setMyCommands",
            json={"commands": commands},
        )


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special chars."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text
