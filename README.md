# 🤖 StockBot — Australian Retail Stock Monitor

A production-ready Telegram bot that monitors EB Games, BIG W, and Target Australia
product pages and instantly alerts you when items come back in stock.

---

## Folder Structure

```
stockbot/
├── main.py                      # FastAPI entry point, scheduler, webhook
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── render.yaml
├── Procfile
├── .env.example
└── app/
    ├── core/
    │   ├── config.py            # Pydantic settings (reads .env)
    │   ├── headers.py           # User-agent rotation
    │   └── logger.py            # Loguru setup
    ├── db/
    │   └── database.py          # Async SQLite via aiosqlite
    ├── scrapers/
    │   ├── base.py              # httpx fetch + tenacity retry
    │   ├── router.py            # Routes URL → correct scraper
    │   ├── ebgames.py           # EB Games AU
    │   ├── bigw.py              # BIG W AU
    │   ├── target_au.py         # Target Australia
    │   └── generic.py           # Fallback for any other retailer
    └── bot/
        ├── handlers.py          # Telegram command handlers
        ├── monitor.py           # Concurrent polling engine
        └── notifier.py          # Telegram alert sender
```

---

## ⚡ Quick Start (Local)

### 1. Clone and set up

```bash
git clone <your-repo>
cd stockbot
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdef...    # from @BotFather
TELEGRAM_CHAT_ID=                          # optional default chat
POLL_INTERVAL_SECONDS=20
MAX_CONCURRENT_CHECKS=15
PROXY_URL=                                 # optional
```

**Get your Bot Token:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot`, follow prompts
3. Copy the token into `.env`

**Get your Chat ID:**
1. Start a chat with your bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find `"chat":{"id": 123456789}` — that number is your chat ID

### 3. Run

```bash
# Development (long-polling, no webhook needed)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or with Docker Compose
docker-compose up --build
```

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/add <url>` | Start tracking a product |
| `/remove <url>` | Stop tracking a product |
| `/list` | Show all tracked products with stock status |
| `/status` | Trigger an immediate stock check now |
| `/help` | Show help |

**Example:**
```
/add https://www.ebgames.com.au/product/pokemon-scarlet-violet-151-ultra-premium-collection
/add https://www.bigw.com.au/product/pokemon-trading-card-game/p/135048
/add https://www.target.com.au/p/pokemon-trading-card-game/66046798
```

---

## 🚀 Deploy to Railway (Recommended)

Railway gives you a persistent disk, free tier, and auto-deploys from GitHub.

### Steps

1. Push your code to a GitHub repo

2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub

3. Set environment variables in the Railway dashboard:
   ```
   TELEGRAM_BOT_TOKEN   = your_token
   WEBHOOK_URL          = https://<your-app>.up.railway.app
   POLL_INTERVAL_SECONDS = 20
   MAX_CONCURRENT_CHECKS = 15
   ```

4. Railway auto-detects `Dockerfile` and deploys.

5. Your `/health` endpoint confirms it's live.

> **Note:** With `WEBHOOK_URL` set, Telegram pushes updates to your bot instantly
> (no polling). This is faster and uses less resources.

---

## 🚀 Deploy to Render

1. Push to GitHub

2. Go to [render.com](https://render.com) → New Web Service → Connect repo

3. Render detects `render.yaml` automatically

4. Add env vars in the Render dashboard:
   ```
   TELEGRAM_BOT_TOKEN
   WEBHOOK_URL   ← set to https://<your-service>.onrender.com
   ```

5. Add a **Disk** (under service settings) mounted at `/app` — this persists `stockbot.db`

---

## 🖥️ Deploy to VPS (Ubuntu)

```bash
# 1. Install Docker
curl -fsSL https://get.docker.com | sh

# 2. Clone repo
git clone <your-repo>
cd stockbot
cp .env.example .env
nano .env   # fill in your values

# 3. If using a domain/HTTPS (required for webhook):
#    Set up nginx + certbot, then set WEBHOOK_URL in .env

# 4. Run
docker-compose up -d

# 5. View logs
docker-compose logs -f
```

**Without a domain (polling mode):** Just leave `WEBHOOK_URL` empty — the bot uses
long-polling automatically. This works perfectly on any VPS or local machine.

---

## 🔒 Proxy Support

To route requests through a proxy (helps with rate limiting):

```env
PROXY_URL=socks5://user:pass@host:1080
# or
PROXY_URL=http://user:pass@host:8080
```

For rotating proxies, services like Webshare or Oxylabs work well.

---

## 📊 How Stock Detection Works

### Priority order (per page):

1. **JSON-LD** (`application/ld+json`) — most reliable, schema.org standard
2. **Next.js / React hydration data** (`__NEXT_DATA__`, `window.__INITIAL_STATE__`)
3. **Meta tags** (`product:availability`)
4. **Add-to-cart button** — checks text and `disabled` attribute
5. **Stock badge/label** CSS selectors
6. **Full page text** — regex fallback

### Anti-bot evasion:

- Rotates User-Agent strings (7 realistic Chrome/Firefox/Safari UAs)
- Realistic `Accept-Language: en-AU` headers
- Random jitter between requests (0.3–1.0s)
- HTTP/2 support via httpx
- Tenacity retry with exponential backoff (3 attempts, 2–8s wait)

### State machine:

```
OOS → IN STOCK    →  Send Telegram alert, mark notified=true
IN STOCK → OOS    →  Reset notified=false (ready for next restock)
No change         →  Update last_check timestamp only
```

Anti-spam: once notified for a restock event, no duplicate alerts
until the item goes OOS and comes back again.

---

## 🛠️ Troubleshooting

**Bot not responding:**
- Check `TELEGRAM_BOT_TOKEN` is correct
- Ensure you've started a chat with the bot first

**Stock always showing OOS:**
- The retailer may use heavy JS rendering — check logs for scraper warnings
- Try `/status` immediately after `/add` to see the live result

**Cloudflare blocks:**
- Add a `PROXY_URL` with a residential proxy
- Increase `POLL_INTERVAL_SECONDS` to 30+

**Database errors on Render/Railway:**
- Ensure a persistent disk is mounted at `/app`
- Without a disk, SQLite resets on every deploy
