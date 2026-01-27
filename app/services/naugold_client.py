"""
Naugold.com Data Client

Fetches price data from https://naugold.com/naugold_td by HTTP scraping
instead of direct WebSocket connection to Polygon.io
"""

import asyncio
import aiohttp
import re
import random
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from loguru import logger


class NaugoldClient:
    """
    HTTP-based client that scrapes price data from naugold.com/naugold_td
    """

    # HTML element ID mapping: asset_type -> (html_id_prefix, symbol_name)
    SYMBOL_MAPPING = {
        'gold': ('xau', 'XAU/USD'),
        'silver': ('xag', 'XAG/USD'),
        'platinum': ('xpt', 'XPT/USD'),
        'palladium': ('xpd', 'XPD/USD'),
        'usd_krw': ('krw', 'USD/KRW'),
        'jpy_krw': ('jpy', 'JPY/KRW'),
        'cny_krw': ('cny', 'CNY/KRW'),
        'eur_krw': ('eur', 'EUR/KRW'),
    }

    # Browser-like headers
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    def __init__(self, callback: Optional[Callable] = None):
        self.provider_name = "massive"
        self.url = "https://naugold.com/naugold_td"
        self.callback = callback
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.base_interval = 25.0  # Base interval 25 seconds
        self.interval_variance = 5.0  # Random variance ±5 seconds

    async def start(self):
        """Start the HTTP polling client"""
        logger.info(f"[{self.provider_name}] Starting Naugold HTTP client (interval: {self.base_interval}±{self.interval_variance}s)")
        self.running = True
        self.session = aiohttp.ClientSession(headers=self.HEADERS)

        try:
            while self.running:
                try:
                    await self._fetch_and_parse()
                except Exception as e:
                    logger.error(f"[{self.provider_name}] Fetch error: {e}")

                # Randomized interval to appear more human-like
                interval = self.base_interval + random.uniform(-self.interval_variance, self.interval_variance)
                await asyncio.sleep(interval)
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        """Stop the client"""
        logger.info(f"[{self.provider_name}] Stopping Naugold HTTP client")
        self.running = False

    async def _fetch_and_parse(self):
        """Fetch the page and parse price data"""
        try:
            # Add Referer to look like normal navigation
            request_headers = {'Referer': 'https://naugold.com/'}

            async with self.session.get(
                self.url,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as response:
                if response.status != 200:
                    logger.warning(f"[{self.provider_name}] HTTP {response.status}")
                    return

                html = await response.text()
                prices = self._parse_html(html)

                for price_data in prices:
                    if self.callback:
                        await self.callback(price_data)

        except asyncio.TimeoutError:
            logger.warning(f"[{self.provider_name}] Request timeout")
        except aiohttp.ClientError as e:
            logger.error(f"[{self.provider_name}] Client error: {e}")

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse HTML to extract price data from naugold.com/naugold_td

        HTML structure uses specific IDs:
        - <span id="xau_bid">5,070.79</span>
        - <span id="xau_ask">5,070.79</span>
        etc.
        """
        prices = []
        timestamp = datetime.utcnow()

        # Parse each symbol using its specific HTML element ID
        for asset_type, (html_id, symbol) in self.SYMBOL_MAPPING.items():
            try:
                # Pattern to match: <span id="xau_bid">5,070.79</span>
                bid_pattern = rf'id="{html_id}_bid"[^>]*>([\d,]+\.?\d*)</span>'
                ask_pattern = rf'id="{html_id}_ask"[^>]*>([\d,]+\.?\d*)</span>'

                bid_match = re.search(bid_pattern, html, re.IGNORECASE)
                ask_match = re.search(ask_pattern, html, re.IGNORECASE)

                if bid_match or ask_match:
                    bid_price = self._parse_price(bid_match.group(1)) if bid_match else None
                    ask_price = self._parse_price(ask_match.group(1)) if ask_match else None

                    # Calculate mid price
                    if bid_price and ask_price:
                        price = (bid_price + ask_price) / 2
                    elif bid_price:
                        price = bid_price
                    elif ask_price:
                        price = ask_price
                    else:
                        continue

                    price_data = {
                        'provider': self.provider_name,
                        'asset_type': asset_type,
                        'price': price,
                        'bid': bid_price,
                        'ask': ask_price,
                        'volume': None,
                        'timestamp': timestamp,
                        'metadata': {
                            'symbol': symbol,
                            'source': 'naugold.com'
                        }
                    }
                    prices.append(price_data)
                    logger.debug(f"[{self.provider_name}] Parsed {symbol}: bid={bid_price}, ask={ask_price}, mid={price:.4f}")

            except Exception as e:
                logger.debug(f"[{self.provider_name}] Failed to parse {asset_type}: {e}")

        if prices:
            logger.info(f"[{self.provider_name}] Fetched {len(prices)} prices from naugold.com")

        return prices

    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string like '5,075.64' to float"""
        try:
            # Remove commas and convert to float
            return float(price_str.replace(',', ''))
        except (ValueError, AttributeError):
            return None
