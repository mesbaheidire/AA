from __future__ import annotations

import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_app
    from telegram_bot_enhanced import EnhancedAliExpressTelegramBot

    bot = EnhancedAliExpressTelegramBot()
    bot_app = bot.application
    await bot_app.initialize()
    await bot_app.start()

    render_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if render_url:
        webhook_url = f"{render_url}/webhook"
        await bot_app.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set: {webhook_url}")
    else:
        logger.warning("RENDER_EXTERNAL_URL not set — webhook not registered")

    yield

    await bot_app.bot.delete_webhook()
    await bot_app.stop()
    await bot_app.shutdown()


web_app = FastAPI(lifespan=lifespan)


@web_app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return Response(status_code=200)


@web_app.get("/")
def root():
    return {"status": "AliExpress Telegram Bot is running!", "mode": "webhook"}


@web_app.get("/health")
def health():
    return {"status": "ok"}


@web_app.get("/check")
async def check():
    if not bot_app:
        return {"error": "Bot not initialized"}
    info = await bot_app.bot.get_webhook_info()
    me = await bot_app.bot.get_me()
    return {
        "bot": me.username,
        "webhook_url": info.url,
        "pending_updates": info.pending_update_count,
        "last_error": info.last_error_message
    }


def main():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
