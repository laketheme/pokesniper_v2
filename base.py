import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup
from loguru import logger
from app.core.headers import random_headers
from app.core.config import settings

TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def _build_client(proxy: str | None = None) -> httpx.AsyncClient:
    kwargs: dict = {
        "timeout": TIMEOUT,
        "follow_redirects": True,
        "http2": True,
    }
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def fetch_page(url: str, proxy: str | None = None) -> tuple[str, int]:
    """Return (html_text, status_code). Raises on non-2xx after retries."""
    headers = random_headers(referer="https://www.google.com.au/")
    async with _build_client(proxy) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        # small human-like jitter
        await asyncio.sleep(0.3 + (hash(url) % 7) * 0.1)
        return resp.text, resp.status_code


def parse_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
