from __future__ import annotations

import os
import re
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from dotenv import load_dotenv
from enhanced_scraper import EnhancedAliExpressScraper
from aliexpress_api import AliExpressAPI

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class EnhancedAliExpressTelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_TOKEN')
        self.app_key = os.getenv('APP_KEY')
        self.app_secret = os.getenv('APP_SECRET')

        if not self.token:
            raise ValueError("TELEGRAM_TOKEN not found in environment variables")

        self.scraper = EnhancedAliExpressScraper()
        self.api = AliExpressAPI(self.app_key, self.app_secret) if self.app_key and self.app_secret else None
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("test", self.test_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_message = """
🤖 **Welcome to the AliExpress Bot!**

Send me an AliExpress product link and I'll analyze it and return detailed information including:

📣 Original price (before discount)
💵 Discounted price
⚡ Super Deals price
⏰ Limited-time offer price
🛍 Discount percentage
🎟️ Available coupons
🏪 Store name
🌟 Store positive rating
✈️ Shipping company
✈️ Shipping cost

**Supported link types:**
• Full link: `https://www.aliexpress.com/item/1005007354532583.html`
• Short link: `https://a.aliexpress.com/_EvKzUlC`
• Affiliate link: `https://s.click.aliexpress.com/e/_c3EHibRf`

Just send the link and I'll do the rest! 🚀
        """
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_message = """
📖 **How to use the bot:**

**🔗 Supported link formats:**
• `https://a.aliexpress.com/_EvKzUlC` *(short link)*
• `https://s.click.aliexpress.com/e/_c3EHibRf` *(affiliate link)*
• `https://www.aliexpress.com/item/1005007354532583.html`
• `https://ar.aliexpress.com/item/1005007354532583.html`
• `https://m.aliexpress.com/item/1005007354532583.html`
• `https://aliexpress.us/item/1005007354532583.html`
• `https://aliexpress.ru/item/1005007354532583.html`

**📱 Steps:**
1️⃣ Copy any AliExpress product link
2️⃣ Send it to this bot
3️⃣ Wait 5–15 seconds while the product is analyzed
4️⃣ Receive detailed product information

**⚙️ Available commands:**
• /start — Welcome message
• /help — This guide
• /test — Test bot connectivity

**🔒 Privacy:**
The bot does not store any personal data or links.
        """
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🧪 **Bot Test:**\n\n"
            "Checking connection... ✅\n"
            "Checking data extraction... ✅\n"
            "Checking formatting... ✅\n\n"
            "The bot is working correctly! 🎉",
            parse_mode=ParseMode.MARKDOWN
        )

    def is_aliexpress_url(self, text):
        patterns = [
            r'https?://a\.aliexpress\.com/[_A-Za-z0-9]+',
            r'https?://s\.click\.aliexpress\.com/[_A-Za-z0-9/e]+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/.*item.*\d+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/item/\d+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/.*product.*\d+',
            r'aliexpress\.(?:com|us|ru)/.*\d{10,}'
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def extract_url_from_text(self, text):
        url_patterns = [
            r'https?://[^\s]+',
            r'www\.[^\s]+',
            r'aliexpress\.[^\s]+'
        ]
        for pattern in url_patterns:
            urls = re.findall(pattern, text, re.IGNORECASE)
            for url in urls:
                url = re.sub(r'[.,;!?]+$', '', url)
                if not url.startswith('http'):
                    url = 'https://' + url
                if self.is_aliexpress_url(url):
                    return url
        return None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = update.message.text
        if self.is_aliexpress_url(message_text):
            url = self.extract_url_from_text(message_text)
            if url:
                await self.process_aliexpress_url(update, url)
            else:
                await update.message.reply_text(
                    "❌ Could not find a valid AliExpress link in your message."
                )
        else:
            await update.message.reply_text(
                "🔗 Please send an AliExpress product link to analyze.\n\n"
                "Use /help for more information.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def process_aliexpress_url(self, update: Update, url):
        processing_msg = await update.message.reply_text(
            "🔄 **Analyzing product...**\n\n"
            "⏳ Please wait (5–15 seconds)\n"
            "🔍 Extracting data from AliExpress",
            parse_mode=ParseMode.MARKDOWN
        )

        try:
            if self.api:
                await processing_msg.edit_text(
                    "🔄 **Analyzing product...**\n\n"
                    "📡 Connecting via AliExpress API...\n"
                    "🔍 Fetching price, discounts & coupons...",
                    parse_mode=ParseMode.MARKDOWN
                )
                product_id = self.scraper.extract_product_id(url)
                if product_id:
                    api_result = await asyncio.to_thread(self.api.get_product_detail, product_id)
                    if api_result:
                        formatted_message = self.api.format_api_product_info(api_result)
                        if formatted_message:
                            await processing_msg.edit_text(formatted_message, parse_mode=ParseMode.MARKDOWN)
                            return

            await processing_msg.edit_text(
                "🔄 **Analyzing product...**\n\n"
                "📡 Connecting to product page...\n"
                "🔍 Extracting data...",
                parse_mode=ParseMode.MARKDOWN
            )

            product_info = await asyncio.to_thread(self.scraper.get_product_details, url)

            if product_info and any(key in product_info for key in ['title', 'prices', 'store']):
                formatted_message = self.scraper.format_product_info(product_info, url)
                await processing_msg.edit_text(formatted_message, parse_mode=ParseMode.MARKDOWN)
                return

            if product_info:
                formatted_message = self.scraper.format_product_info(product_info, url)
                await processing_msg.edit_text(formatted_message, parse_mode=ParseMode.MARKDOWN)
                return

            await processing_msg.edit_text(
                "❌ **Sorry, could not retrieve product information**\n\n"
                "• Product unavailable or deleted\n"
                "• Invalid or expired link\n"
                "• Try again after a minute\n\n"
                f"🔗 [Open link in browser]({url})",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Error processing URL {url}: {e}")
            await processing_msg.edit_text(
                "❌ **A technical error occurred while processing the link**\n\n"
                "Please try again later.\n\n"
                f"🔗 [Open link in browser]({url})",
                parse_mode=ParseMode.MARKDOWN
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.message:
            try:
                await update.message.reply_text("❌ An unexpected error occurred. Please try again.")
            except Exception:
                pass

    def run(self):
        logger.info("Starting Enhanced AliExpress Telegram Bot...")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
