from __future__ import annotations

import os
import threading
import logging
import requests
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

web_app = FastAPI()


@web_app.get("/")
def root():
    return {"status": "AliExpress Telegram Bot is running!", "bot": "active"}


@web_app.get("/health")
def health():
    return {"status": "ok"}


@web_app.get("/check")
def check():
    token = os.getenv("TELEGRAM_TOKEN", "NOT_SET")
    result = {
        "token_set": token != "NOT_SET",
        "token_preview": token[:10] + "..." if len(token) > 10 else token,
        "telegram_reachable": False,
        "token_valid": False,
        "error": None
    }
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getMe",
            timeout=10
        )
        result["telegram_reachable"] = True
        data = resp.json()
        result["token_valid"] = data.get("ok", False)
        if data.get("ok"):
            result["bot_name"] = data["result"].get("username")
        else:
            result["error"] = data.get("description")
    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT - Render is blocking Telegram"
    except Exception as e:
        result["error"] = str(e)
    return result


def run_bot():
    try:
        from telegram_bot_enhanced import EnhancedAliExpressTelegramBot
        bot = EnhancedAliExpressTelegramBot()
        logger.info("Starting bot with polling...")
        bot.run()
    except Exception as e:
        logger.error(f"Bot error: {e}")


def main():
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Web server starting on port {port}")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
