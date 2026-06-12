# AliExpress Discount Bot

Telegram bot that analyzes AliExpress product links and returns detailed pricing info.

## Features
- Original & discounted prices
- Super Deals & limited-time offers
- Available coupons
- Store info & ratings
- Shipping details

## Supported Links
- Full links: `https://www.aliexpress.com/item/...`
- Short links: `https://a.aliexpress.com/...`
- Affiliate links: `https://s.click.aliexpress.com/...`

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | ✅ Yes | Bot token from @BotFather |
| `APP_KEY` | ❌ Optional | AliExpress API key |
| `APP_SECRET` | ❌ Optional | AliExpress API secret |

## Deploy on Render
1. Push this repo to GitHub
2. Connect to [render.com](https://render.com)
3. New Web Service → Docker
4. Add environment variables
5. Deploy
