from __future__ import annotations

import requests
import hashlib
import hmac
import time
import re
import logging

logger = logging.getLogger(__name__)


class AliExpressAPI:
    BASE_URL = "https://api-sg.aliexpress.com/sync"

    def __init__(self, app_key, app_secret):
        self.app_key = app_key
        self.app_secret = app_secret

    def _sign(self, params: dict) -> str:
        method = params.get("method", "")
        sorted_items = sorted(
            [(k, v) for k, v in params.items() if k != "sign"],
            key=lambda x: x[0]
        )
        concat = method + "".join(f"{k}{v}" for k, v in sorted_items)
        sig = hmac.new(
            self.app_secret.encode("utf-8"),
            concat.encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()
        return sig

    def _base_params(self, method: str) -> dict:
        return {
            "app_key": self.app_key,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "sha256",
            "method": method,
        }

    def _call(self, method: str, extra: dict) -> dict | None:
        params = self._base_params(method)
        params.update(extra)
        params["sign"] = self._sign(params)
        try:
            resp = requests.post(self.BASE_URL, data=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"API call failed [{method}]: {e}")
            return None

    def get_product_detail(self, product_id: str) -> dict | None:
        return self._call(
            "aliexpress.affiliate.productdetail.get",
            {
                "product_ids": str(product_id),
                "fields": (
                    "product_id,product_title,sale_price,original_price,"
                    "discount,evaluate_rate,product_detail_url,"
                    "shop_id,shop_url,commission_rate,"
                    "hot_product_commission_rate,target_sale_price,"
                    "target_original_price,target_sale_price_currency"
                ),
                "target_currency": "USD",
                "target_language": "EN",
                "tracking_id": "default",
            },
        )

    def search_products(self, keywords: str, page_no: int = 1, page_size: int = 20) -> dict | None:
        return self._call(
            "aliexpress.affiliate.product.query",
            {
                "keywords": keywords,
                "page_no": str(page_no),
                "page_size": str(page_size),
                "target_currency": "USD",
                "target_language": "EN",
                "tracking_id": "default",
            },
        )

    def get_hotproducts(self, category_id: str = "", page_no: int = 1) -> dict | None:
        params = {
            "page_no": str(page_no),
            "page_size": "20",
            "target_currency": "USD",
            "target_language": "EN",
            "tracking_id": "default",
        }
        if category_id:
            params["category_ids"] = category_id
        return self._call("aliexpress.affiliate.hotproduct.query", params)

    def extract_product_id_from_url(self, url: str) -> str | None:
        patterns = [
            r"/item/(\d+)",
            r"productId=(\d+)",
            r"/(\d+)\.html",
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def format_api_product_info(self, api_response: dict) -> str | None:
        if not api_response:
            return None
        try:
            resp = api_response.get("aliexpress_affiliate_productdetail_get_response", {})
            result = resp.get("result", {})
            products = result.get("products", {}).get("product", [])
            if not products:
                return None

            p = products[0]
            message = "🛍 **AliExpress Product Info**\n\n"

            title = p.get("product_title", "")
            if title:
                title = title[:200] + "..." if len(title) > 200 else title
                message += f"📦 **Product:** {title}\n\n"

            currency = p.get("target_sale_price_currency", "USD")
            orig = p.get("target_original_price") or p.get("original_price", "")
            sale = p.get("target_sale_price") or p.get("sale_price", "")

            if orig:
                message += f"📣 Original Price: {orig} {currency}\n"
            if sale:
                message += f"💵 Discounted Price: {sale} {currency}\n"

            discount = p.get("discount", "")
            if discount:
                message += f"🛍 Discount: {discount}%\n"
            elif orig and sale:
                try:
                    o = float(re.sub(r"[^\d.]", "", str(orig)))
                    s = float(re.sub(r"[^\d.]", "", str(sale)))
                    if o > 0 and s > 0 and o > s:
                        message += f"🛍 Discount: {((o - s) / o * 100):.1f}%\n"
                except (ValueError, TypeError):
                    pass

            commission = p.get("commission_rate") or p.get("hot_product_commission_rate", "")
            if commission:
                message += f"💼 Commission Rate: {commission}%\n"

            shop_id = p.get("shop_id", "")
            if shop_id:
                message += f"\n🏪 Store ID: {shop_id}\n"

            rating = p.get("evaluate_rate", "")
            if rating:
                message += f"🌟 Positive Rating: {rating}%\n"

            link = p.get("product_detail_url", "")
            if link:
                message += f"\n🔗 [Product Link]({link})"

            return message
        except Exception as e:
            logger.error(f"Error formatting API product info: {e}")
            return None
