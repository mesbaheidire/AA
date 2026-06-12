from __future__ import annotations

import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urlparse, parse_qs, unquote
from fake_useragent import UserAgent
import time
import random
import logging

logger = logging.getLogger(__name__)


class EnhancedAliExpressScraper:
    def __init__(self):
        self.ua = UserAgent()
        self.session = requests.Session()
        self.update_headers()

    def update_headers(self):
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })

    def is_short_url(self, url):
        patterns = [
            r'https?://a\.aliexpress\.com/[_A-Za-z0-9]+',
            r'https?://s\.click\.aliexpress\.com/e/[_A-Za-z0-9]+',
            r'https?://s\.click\.aliexpress\.com/[_A-Za-z0-9/]+',
        ]
        for p in patterns:
            if re.search(p, url, re.IGNORECASE):
                return True
        return False

    def resolve_short_url(self, url):
        try:
            resp = self.session.head(url, timeout=15, allow_redirects=True)
            resolved = resp.url
            logger.info(f"Resolved short URL: {url} -> {resolved}")
            return resolved
        except Exception:
            try:
                resp = self.session.get(url, timeout=15, allow_redirects=True)
                return resp.url
            except Exception as e:
                logger.error(f"Failed to resolve short URL {url}: {e}")
                return url

    def extract_product_id(self, url):
        try:
            url = unquote(url)
            if self.is_short_url(url):
                url = self.resolve_short_url(url)
            patterns = [
                r'/item/(\d+)',
                r'productId[=:](\d+)',
                r'/(\d+)\.html',
                r'item_id[=:](\d+)',
                r'product[_-]?id[=:](\d+)'
            ]
            for pattern in patterns:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting product ID: {e}")
            return None

    def normalize_url(self, url):
        if not url.startswith('http'):
            url = 'https://' + url
        if self.is_short_url(url):
            url = self.resolve_short_url(url)
        url = url.replace('m.aliexpress.com', 'www.aliexpress.com')
        url = url.replace('ar.aliexpress.com', 'www.aliexpress.com')
        return url

    def get_product_details(self, url):
        try:
            url = self.normalize_url(url)
            time.sleep(random.uniform(2, 4))
            self.update_headers()

            for attempt in range(3):
                try:
                    response = self.session.get(url, timeout=30, allow_redirects=True)
                    if response.status_code == 200:
                        break
                    elif response.status_code == 403:
                        logger.warning(f"Access denied (403), attempt {attempt + 1}")
                        time.sleep(random.uniform(5, 10))
                        self.update_headers()
                    else:
                        logger.warning(f"HTTP {response.status_code}, attempt {attempt + 1}")
                        time.sleep(random.uniform(3, 7))
                except requests.RequestException as e:
                    logger.error(f"Request error on attempt {attempt + 1}: {e}")
                    if attempt < 2:
                        time.sleep(random.uniform(5, 10))
                    else:
                        raise

            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            product_data = (
                self.extract_from_json_ld(soup) or
                self.extract_from_meta_tags(soup) or
                self.extract_from_scripts(soup) or
                self.extract_from_html_elements(soup)
            )
            return product_data

        except Exception as e:
            logger.error(f"Error scraping product: {e}")
            return self.create_fallback_data(url)

    def extract_from_json_ld(self, soup):
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        return self.parse_json_ld_product(data)
            return None
        except Exception as e:
            logger.error(f"Error extracting JSON-LD: {e}")
            return None

    def parse_json_ld_product(self, data):
        try:
            product_info = {}
            product_info['title'] = data.get('name', '')
            product_info['description'] = data.get('description', '')
            offers = data.get('offers', {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if offers:
                product_info['prices'] = {
                    'price': offers.get('price', ''),
                    'currency': offers.get('priceCurrency', 'USD'),
                    'availability': offers.get('availability', '')
                }
            brand = data.get('brand', {})
            if isinstance(brand, dict):
                product_info['store'] = {'name': brand.get('name', '')}
            return product_info
        except Exception as e:
            logger.error(f"Error parsing JSON-LD product: {e}")
            return None

    def extract_from_meta_tags(self, soup):
        try:
            product_info = {}
            title_meta = soup.find('meta', property='og:title') or soup.find('meta', {'name': 'title'})
            if title_meta:
                product_info['title'] = title_meta.get('content', '')
            price_meta = soup.find('meta', property='product:price:amount')
            if price_meta:
                currency_meta = soup.find('meta', property='product:price:currency')
                product_info['prices'] = {
                    'price': price_meta.get('content', ''),
                    'currency': currency_meta.get('content', 'USD') if currency_meta else 'USD'
                }
            return product_info if product_info else None
        except Exception as e:
            logger.error(f"Error extracting meta tags: {e}")
            return None

    def extract_from_scripts(self, soup):
        try:
            scripts = soup.find_all('script')
            for script in scripts:
                if not script.string:
                    continue
                patterns = [
                    r'window\.runParams\s*=\s*({.+?});\s*(?:var\s|window\.|//)',
                    r'window\.runParams\s*=\s*({.+?});',
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                    r'window\.pageData\s*=\s*({.+?});',
                    r'var\s+pageData\s*=\s*({.+?});',
                    r'"data"\s*:\s*(\{.+?"titleModule".+?\})\s*[,}]',
                ]
                for pattern in patterns:
                    match = re.search(pattern, script.string, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            parsed = self.parse_script_data(data)
                            if parsed:
                                return parsed
                        except json.JSONDecodeError:
                            continue
                coupon_match = re.search(
                    r'"couponModule"\s*:\s*(\{.*?"couponList".*?\})\s*,\s*"',
                    script.string, re.DOTALL
                )
                if coupon_match:
                    try:
                        coupon_data = json.loads(coupon_match.group(1))
                        coupons = self._parse_coupon_module(coupon_data)
                        if coupons:
                            return {'coupons': coupons}
                    except json.JSONDecodeError:
                        pass
            return None
        except Exception as e:
            logger.error(f"Error extracting from scripts: {e}")
            return None

    def parse_script_data(self, data):
        try:
            product_info = {}
            if 'data' in data:
                data = data['data']

            title_sources = [
                data.get('titleModule', {}).get('subject'),
                data.get('title'),
                data.get('productTitle'),
                data.get('name')
            ]
            for title in title_sources:
                if title:
                    product_info['title'] = title
                    break

            price_module = data.get('priceModule', {})
            if price_module:
                prices = {
                    'min_price': self._price_val(price_module.get('minActivityAmount')),
                    'max_price': self._price_val(price_module.get('maxActivityAmount')),
                    'original_price': self._price_val(price_module.get('minAmount')),
                    'currency': self._currency(price_module.get('minAmount'))
                }
                discount_pct = price_module.get('discount') or price_module.get('discountPercent')
                if discount_pct:
                    prices['discount_percent'] = str(discount_pct)
                activity_amount = price_module.get('activityAmount')
                if activity_amount:
                    prices['super_deal_price'] = self._price_val(activity_amount)
                product_info['prices'] = prices

            store_module = data.get('storeModule', {})
            if store_module:
                product_info['store'] = {
                    'name': store_module.get('storeName', ''),
                    'rating': store_module.get('positiveRate', ''),
                    'id': store_module.get('storeNum', '')
                }

            shipping_module = data.get('shippingModule', {})
            if shipping_module:
                freight_info = shipping_module.get('generalFreightInfo', {})
                layout_list = freight_info.get('originalLayoutResultList', [])
                if layout_list:
                    biz = layout_list[0].get('bizData', {})
                    product_info['shipping'] = {
                        'company': biz.get('deliveryOptionCode', ''),
                        'cost': biz.get('formattedAmount', '')
                    }

            coupon_module = data.get('couponModule', {})
            if coupon_module:
                coupons = self._parse_coupon_module(coupon_module)
                if coupons:
                    product_info['coupons'] = coupons

            activity_module = data.get('activityModule', {})
            if activity_module:
                ltd = activity_module.get('limitedTimeDeal', {})
                if ltd:
                    product_info['limited_deal'] = {
                        'price': self._price_val(ltd.get('activityPrice') or ltd.get('price')),
                        'discount': ltd.get('discount') or ltd.get('discountPercent', '')
                    }

            common_module = data.get('commonModule', {})
            if common_module and common_module.get('isSuperDeal'):
                product_info['is_super_deal'] = True

            return product_info if product_info else None
        except Exception as e:
            logger.error(f"Error parsing script data: {e}")
            return None

    def _parse_coupon_module(self, coupon_module):
        try:
            coupon_list = coupon_module.get('couponList', [])
            result = []
            for c in coupon_list[:5]:
                discount = c.get('discount') or c.get('couponDiscount') or c.get('discountAmount', '')
                min_amt = c.get('minAmount') or c.get('minOrderAmount', {})
                min_val = self._price_val(min_amt) if isinstance(min_amt, dict) else str(min_amt)
                currency = self._currency(c.get('minAmount', {})) if isinstance(c.get('minAmount'), dict) else 'USD'
                if discount:
                    result.append({
                        'discount': str(discount),
                        'min_amount': min_val,
                        'currency': currency
                    })
            return result if result else None
        except Exception:
            return None

    def extract_from_html_elements(self, soup):
        try:
            product_info = {}
            title_selectors = [
                'h1[data-pl="product-title"]', 'h1.product-title-text',
                '.product-title', 'h1', '.pdp-product-name'
            ]
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    product_info['title'] = title_elem.get_text(strip=True)
                    break

            price_selectors = [
                '.notranslate', '[class*="price"]',
                '[class*="amount"]', '[data-spm-anchor-id*="price"]'
            ]
            prices = []
            for selector in price_selectors:
                for elem in soup.select(selector):
                    text = elem.get_text(strip=True)
                    price_matches = re.findall(r'[\$€£¥₹]\s*[\d,]+\.?\d*', text)
                    prices.extend(price_matches)
            if prices:
                product_info['prices'] = {'extracted_prices': list(set(prices))}

            store_selectors = ['.shop-name', '.store-name', '[class*="store"]', '[class*="shop"]']
            for selector in store_selectors:
                store_elem = soup.select_one(selector)
                if store_elem:
                    product_info['store'] = {'name': store_elem.get_text(strip=True)}
                    break

            coupon_selectors = [
                '[class*="coupon"]', '[class*="discount"]',
                '[class*="voucher"]', '[class*="promo"]'
            ]
            coupons_found = []
            for selector in coupon_selectors:
                for elem in soup.select(selector)[:3]:
                    text = elem.get_text(strip=True)
                    if text and len(text) < 80 and any(c.isdigit() for c in text):
                        coupons_found.append(text)
            if coupons_found:
                product_info['raw_coupons'] = list(set(coupons_found))

            return product_info if product_info else None
        except Exception as e:
            logger.error(f"Error extracting from HTML: {e}")
            return None

    def _price_val(self, price_obj):
        if price_obj is None:
            return ''
        if isinstance(price_obj, dict):
            return str(price_obj.get('value', price_obj.get('formattedAmount', '')))
        return str(price_obj)

    def _currency(self, price_obj):
        if isinstance(price_obj, dict):
            return price_obj.get('currency', 'USD')
        return 'USD'

    def extract_price_value(self, price_obj):
        return self._price_val(price_obj)

    def extract_currency(self, price_obj):
        return self._currency(price_obj)

    def create_fallback_data(self, url):
        product_id = self.extract_product_id(url)
        return {
            'title': f'AliExpress Product - {product_id}' if product_id else 'AliExpress Product',
            'url': url,
            'status': 'Link found but full details could not be retrieved'
        }

    def is_aliexpress_url(self, text):
        aliexpress_patterns = [
            r'https?://a\.aliexpress\.com/[_A-Za-z0-9]+',
            r'https?://s\.click\.aliexpress\.com/[_A-Za-z0-9/e]+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/.*item.*\d+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/item/\d+',
            r'https?://(?:www\.|m\.|ar\.|[a-z]{2}\.)?aliexpress\.(?:com|us|ru)/.*product.*\d+',
            r'aliexpress\.(?:com|us|ru)/.*\d{10,}'
        ]
        for pattern in aliexpress_patterns:
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
            for url in re.findall(pattern, text, re.IGNORECASE):
                url = re.sub(r'[.,;!?]+$', '', url)
                if not url.startswith('http'):
                    url = 'https://' + url
                if self.is_aliexpress_url(url):
                    return url
        return None

    def format_product_info(self, product_data, url):
        if not product_data:
            return "❌ Could not retrieve product information."

        message = "🛍 **AliExpress Product Info**\n\n"

        if product_data.get('title'):
            title = product_data['title']
            title = title[:200] + "..." if len(title) > 200 else title
            message += f"📦 **Product:** {title}\n\n"

        if product_data.get('is_super_deal'):
            message += "⚡ **Super Deal!**\n"

        if 'prices' in product_data:
            prices = product_data['prices']
            if isinstance(prices, dict):
                currency = prices.get('currency', 'USD')
                if prices.get('original_price'):
                    message += f"📣 Original Price: {prices['original_price']} {currency}\n"
                if prices.get('min_price'):
                    message += f"💵 Discounted Price: {prices['min_price']} {currency}\n"
                if prices.get('max_price') and prices['max_price'] != prices.get('min_price'):
                    message += f"💵 Max Price: {prices['max_price']} {currency}\n"
                if prices.get('super_deal_price'):
                    message += f"⚡ Super Deal Price: {prices['super_deal_price']} {currency}\n"
                if prices.get('price'):
                    message += f"💵 Price: {prices['price']} {currency}\n"
                if prices.get('discount_percent'):
                    message += f"🛍 Discount: {prices['discount_percent']}%\n"
                elif prices.get('original_price') and prices.get('min_price'):
                    try:
                        orig = float(re.sub(r'[^\d.]', '', str(prices['original_price'])))
                        disc = float(re.sub(r'[^\d.]', '', str(prices['min_price'])))
                        if orig > 0 and disc > 0 and orig > disc:
                            pct = ((orig - disc) / orig) * 100
                            message += f"🛍 Discount: {pct:.1f}%\n"
                    except (ValueError, TypeError):
                        pass
                if 'extracted_prices' in prices:
                    message += "💵 Available Prices:\n"
                    for p in prices['extracted_prices'][:3]:
                        message += f"   • {p}\n"

        if 'limited_deal' in product_data:
            ltd = product_data['limited_deal']
            message += "\n⏰ **Limited-Time Deal:**\n"
            if ltd.get('price'):
                message += f"   💥 Deal Price: {ltd['price']}\n"
            if ltd.get('discount'):
                message += f"   🔥 Deal Discount: {ltd['discount']}%\n"

        if 'coupons' in product_data:
            message += "\n🎟️ **Available Coupons:**\n"
            for c in product_data['coupons']:
                line = f"   • {c['discount']} off"
                if c.get('min_amount'):
                    line += f" (min. order: {c['min_amount']} {c.get('currency', '')})"
                message += line + "\n"

        if 'raw_coupons' in product_data and 'coupons' not in product_data:
            message += "\n🎟️ **Promotions found:**\n"
            for c in product_data['raw_coupons'][:3]:
                message += f"   • {c}\n"

        if 'store' in product_data:
            store = product_data['store']
            message += "\n"
            if store.get('name'):
                message += f"🏪 Store: {store['name']}\n"
            if store.get('rating'):
                message += f"🌟 Positive Rating: {store['rating']}%\n"
            if store.get('id'):
                message += f"🆔 Store ID: {store['id']}\n"

        if 'shipping' in product_data:
            shipping = product_data['shipping']
            if shipping.get('company'):
                message += f"✈️ Shipping Company: {shipping['company']}\n"
            if shipping.get('cost'):
                message += f"✈️ Shipping Cost: {shipping['cost']}\n"

        if 'status' in product_data:
            message += f"\n⚠️ {product_data['status']}\n"

        message += f"\n🔗 [Product Link]({url})"
        return message
