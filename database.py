import aiosqlite
from loguru import logger
from app.core.config import settings

DB_PATH = settings.database_url.replace("sqlite+aiosqlite:///", "")

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL DEFAULT 'Unknown Product',
    retailer    TEXT    NOT NULL DEFAULT 'unknown',
    in_stock    INTEGER NOT NULL DEFAULT 0,   -- 0=unknown/oos, 1=in stock
    notified    INTEGER NOT NULL DEFAULT 0,   -- 1 = notified for current restock
    added_by    TEXT,                          -- telegram user_id
    chat_id     TEXT,                          -- where to send notification
    last_check  TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL,
    event       TEXT    NOT NULL,  -- 'in_stock' | 'out_of_stock'
    notified_at TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_PRODUCTS_TABLE)
        await db.execute(CREATE_ALERTS_TABLE)
        await db.commit()
    logger.info("Database initialised at {}", DB_PATH)


async def add_product(url: str, name: str, retailer: str, added_by: str, chat_id: str) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute(
                """INSERT INTO products (url, name, retailer, added_by, chat_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (url, name, retailer, added_by, chat_id),
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None  # already tracked


async def remove_product(url: str, chat_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM products WHERE url = ? AND chat_id = ?", (url, chat_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def list_products(chat_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM products WHERE chat_id = ? ORDER BY id", (chat_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_products() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM products")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_product_stock(
    product_id: int,
    in_stock: bool,
    notified: bool,
    name: str | None = None,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if name:
            await db.execute(
                """UPDATE products
                   SET in_stock=?, notified=?, name=?, last_check=datetime('now')
                   WHERE id=?""",
                (int(in_stock), int(notified), name, product_id),
            )
        else:
            await db.execute(
                """UPDATE products
                   SET in_stock=?, notified=?, last_check=datetime('now')
                   WHERE id=?""",
                (int(in_stock), int(notified), product_id),
            )
        await db.commit()


async def log_alert(product_id: int, event: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO alerts (product_id, event) VALUES (?, ?)",
            (product_id, event),
        )
        await db.commit()
